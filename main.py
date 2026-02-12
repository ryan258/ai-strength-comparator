"""
AI Ethics Comparator - Main Server
App factory with startup-time service initialization.
"""

import io
import logging
import os
import random
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lib.ai_service import AIService
from lib.analysis import AnalysisConfig, AnalysisEngine
from lib.config import AppConfig
from lib.paradoxes import extract_scenario_text, get_paradox_by_id, load_paradoxes
from lib.query_processor import QueryProcessor, RunConfig
from lib.reporting import ReportGenerator
from lib.storage import RunStorage, STRICT_RUN_ID_PATTERN
from lib.validation import InsightRequest, QueryRequest
from lib.view_models import RunViewModel, fetch_recent_run_view_models, safe_markdown

# Load environment before startup config resolution.
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_NAME_PATTERN = re.compile(r"^[a-z0-9\-_/:.]+$", re.IGNORECASE)
RUN_ID_PATTERN = STRICT_RUN_ID_PATTERN


@dataclass
class AppServices:
    config: AppConfig
    storage: RunStorage
    query_processor: QueryProcessor
    analysis_engine: AnalysisEngine
    report_generator: ReportGenerator
    templates: Jinja2Templates
    paradoxes_path: Path


def _build_templates(templates_dir: str) -> Jinja2Templates:
    templates = Jinja2Templates(directory=templates_dir)
    templates.env.filters["markdown"] = safe_markdown
    return templates


def _validate_run_id(run_id: str) -> None:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id")


def _get_services(request: Request) -> AppServices:
    services: Optional[AppServices] = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    return services


def create_app(config_override: Optional[AppConfig] = None) -> FastAPI:
    templates_dir = "templates"
    templates = _build_templates(templates_dir)
    paradoxes_path = Path(__file__).parent / "paradoxes.json"
    analysis_prompt_path = Path(__file__).parent / templates_dir / "analysis_prompt.txt"

    if config_override is not None:
        app_title = config_override.APP_NAME
        app_version = config_override.VERSION
        allowed_origins = [config_override.APP_BASE_URL] if config_override.APP_BASE_URL else []
    else:
        app_title = "AI Ethics Comparator"
        app_version = "0.0.0"
        app_base_url = os.getenv("APP_BASE_URL")
        allowed_origins = [app_base_url] if app_base_url else []

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
        config = config_override or AppConfig.load()
        try:
            config.validate_secrets()
        except ValueError as exc:
            logger.critical(str(exc))
            raise RuntimeError(str(exc)) from exc

        ai_service = AIService(
            api_key=str(config.OPENROUTER_API_KEY),
            base_url=config.OPENROUTER_BASE_URL,
            referer=config.APP_BASE_URL,
            app_name=config.APP_NAME,
            max_retries=config.AI_MAX_RETRIES,
            retry_delay=config.AI_RETRY_DELAY,
        )

        storage = RunStorage(str(config.results_path))
        migrated_ids = await storage.migrate_legacy_run_ids()
        if migrated_ids:
            logger.info("Migrated %s legacy run IDs to strict format", len(migrated_ids))

        query_processor = QueryProcessor(
            ai_service,
            concurrency_limit=config.AI_CONCURRENCY_LIMIT,
            choice_inference_model=(
                config.ANALYST_MODEL if config.AI_CHOICE_INFERENCE_ENABLED else None
            ),
        )
        analysis_engine = AnalysisEngine(
            ai_service,
            prompt_template_path=analysis_prompt_path,
        )
        report_generator = ReportGenerator(templates_dir=templates_dir)

        app_instance.state.services = AppServices(
            config=config,
            storage=storage,
            query_processor=query_processor,
            analysis_engine=analysis_engine,
            report_generator=report_generator,
            templates=templates,
            paradoxes_path=paradoxes_path,
        )
        app_instance.title = config.APP_NAME
        app_instance.version = config.VERSION
        logger.info("Starting %s v%s", config.APP_NAME, config.VERSION)
        try:
            yield
        finally:
            app_instance.state.services = None

    app = FastAPI(title=app_title, version=app_version, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-App-Version"],
    )

    app.state.services = None

    @app.middleware("http")
    async def add_version_header(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response: Response = await call_next(request)
        services: Optional[AppServices] = getattr(request.app.state, "services", None)
        if services is not None:
            response.headers["X-App-Version"] = services.config.VERSION
        return response

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        services = _get_services(request)
        config = services.config
        try:
            paradoxes = load_paradoxes(services.paradoxes_path)
        except Exception as exc:
            logger.error("Failed to load paradoxes: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="Failed to load paradox definitions. Please check server logs.",
            ) from exc

        recent_run_contexts = await fetch_recent_run_view_models(
            services.storage,
            paradoxes,
            config.ANALYST_MODEL,
        )

        initial_paradox = random.choice(paradoxes) if paradoxes else None
        initial_scenario_text = ""
        if initial_paradox:
            initial_scenario_text = extract_scenario_text(
                initial_paradox.get("promptTemplate", "")
            )

        return services.templates.TemplateResponse(
            request,
            "index.html",
            {
                "paradoxes": paradoxes,
                "models": config.AVAILABLE_MODELS,
                "default_model": config.DEFAULT_MODEL,
                "recent_run_contexts": recent_run_contexts,
                "initial_paradox": initial_paradox,
                "initial_scenario_text": initial_scenario_text,
                "max_iterations": config.MAX_ITERATIONS,
            },
        )

    @app.get("/health")
    async def health_check(request: Request) -> dict:
        services: Optional[AppServices] = getattr(request.app.state, "services", None)
        version = services.config.VERSION if services else "uninitialized"
        return {
            "status": "healthy" if services else "starting",
            "version": version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime": "N/A",
        }

    @app.get("/api/paradoxes")
    async def get_paradoxes(request: Request) -> list:
        services = _get_services(request)
        try:
            return load_paradoxes(services.paradoxes_path)
        except Exception as exc:
            logger.error("Failed to read paradoxes: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to read paradoxes.") from exc

    @app.get("/api/fragments/paradox-details")
    async def get_paradox_details(request: Request, paradoxId: str) -> HTMLResponse:
        services = _get_services(request)
        try:
            paradoxes = load_paradoxes(services.paradoxes_path)
            paradox = get_paradox_by_id(paradoxes, paradoxId)
            if not paradox:
                return HTMLResponse("<div>Paradox not found</div>", status_code=404)

            scenario_text = extract_scenario_text(paradox.get("promptTemplate", ""))
            return services.templates.TemplateResponse(
                request,
                "partials/paradox_details.html",
                {
                    "paradox": paradox,
                    "scenario_text": scenario_text,
                },
            )
        except Exception as exc:
            logger.error("Failed to get paradox details: %s", exc)
            return HTMLResponse("<div>Error loading details</div>", status_code=500)

    @app.get("/api/runs")
    async def list_runs(request: Request) -> list:
        services = _get_services(request)
        try:
            return await services.storage.list_runs()
        except Exception as exc:
            logger.error("Failed to list runs: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to retrieve runs.") from exc

    @app.get("/api/runs/{run_id}")
    async def get_run(request: Request, run_id: str) -> dict:
        services = _get_services(request)
        _validate_run_id(run_id)
        try:
            return await services.storage.get_run(run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run not found.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Failed to get run %s: %s", run_id, exc)
            raise HTTPException(status_code=500, detail="Failed to retrieve run data.") from exc

    @app.post("/api/query")
    async def execute_query(request: Request, query_request: QueryRequest):
        services = _get_services(request)
        config = services.config
        try:
            paradoxes = load_paradoxes(services.paradoxes_path)
            paradox = get_paradox_by_id(paradoxes, query_request.paradox_id)
            if not paradox:
                raise HTTPException(
                    status_code=404,
                    detail=f"Paradox '{query_request.paradox_id}' not found",
                )

            req_iterations = query_request.iterations or 10
            if req_iterations > config.MAX_ITERATIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Iterations {req_iterations} exceeds limit of {config.MAX_ITERATIONS}"
                    ),
                )

            run_config = RunConfig(
                modelName=query_request.model_name,
                paradox=paradox,
                option_overrides=(
                    [opt.model_dump() for opt in query_request.option_overrides.options]
                    if query_request.option_overrides and query_request.option_overrides.options
                    else None
                ),
                iterations=req_iterations,
                systemPrompt=query_request.system_prompt or "",
                params=query_request.params.model_dump() if query_request.params else {},
            )

            run_data = await services.query_processor.execute_run(run_config)

            run_id = await services.storage.generate_run_id(query_request.model_name)
            run_data["runId"] = run_id
            await services.storage.save_run(run_id, run_data)

            if request.headers.get("HX-Request"):
                vm = RunViewModel.build(run_data, paradox)
                vm["config_analyst_model"] = config.ANALYST_MODEL
                return services.templates.TemplateResponse(
                    request,
                    "partials/result_item.html",
                    {"ctx": vm},
                )

            return run_data
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Query execution failed: %s", exc)
            error_str = str(exc).lower()
            if "401" in error_str or "unauthorized" in error_str:
                raise HTTPException(status_code=401, detail="Invalid API Key or Unauthorized.") from exc
            if "429" in error_str or "rate limit" in error_str:
                raise HTTPException(status_code=429, detail="Rate limit exceeded. Try fewer iterations.") from exc
            if "insufficient_quota" in error_str or "quota" in error_str:
                raise HTTPException(status_code=402, detail="Insufficient API credits.") from exc
            raise HTTPException(status_code=500, detail="Internal server error") from exc

    @app.post("/api/insight")
    async def generate_insight(request: Request, insight_request: InsightRequest) -> dict:
        services = _get_services(request)
        try:
            model_to_use = insight_request.analystModel or services.config.ANALYST_MODEL
            cfg = AnalysisConfig(
                run_data=insight_request.runData,
                analyst_model=model_to_use,
            )
            insight_data = await services.analysis_engine.generate_insight(cfg)

            if "runId" in insight_request.runData:
                run_id = insight_request.runData["runId"]
                if RUN_ID_PATTERN.fullmatch(run_id):
                    try:
                        existing_run = await services.storage.get_run(run_id)
                        if "insights" not in existing_run:
                            existing_run["insights"] = []
                        existing_run["insights"].append(insight_data)
                        await services.storage.save_run(run_id, existing_run)
                    except Exception as save_error:
                        logger.error("Error saving insight: %s", save_error)

            return {"insight": insight_data["content"], "model": model_to_use}
        except Exception as exc:
            logger.error("Insight generation failed: %s", exc)
            raise HTTPException(status_code=500, detail="Internal server error") from exc

    @app.post("/api/runs/{run_id}/analyze")
    async def analyze_run(request: Request, run_id: str, regenerate: bool = False) -> HTMLResponse:
        services = _get_services(request)
        _validate_run_id(run_id)
        model_to_use = services.config.ANALYST_MODEL
        try:
            form_data = await request.form()
            requested_analyst = form_data.get("analyst_model")
            if requested_analyst and not MODEL_NAME_PATTERN.match(requested_analyst):
                return HTMLResponse("<div class='error'>Invalid model name format</div>", status_code=400)

            run_data = await services.storage.get_run(run_id)

            if not regenerate and "insights" in run_data and run_data["insights"]:
                insight = run_data["insights"][-1]
                cached_model = insight.get("analystModel")
                if not requested_analyst or requested_analyst == cached_model:
                    content = insight.get("content", {})
                    if isinstance(content, str):
                        content = {"legacy_text": content}
                    return services.templates.TemplateResponse(
                        request,
                        "partials/analysis_view.html",
                        {
                            "insight": content,
                            "model": cached_model,
                            "cached": True,
                            "run_id": run_id,
                            "run_data": run_data,
                        },
                    )

            model_to_use = requested_analyst or services.config.ANALYST_MODEL
            if not model_to_use or not MODEL_NAME_PATTERN.match(model_to_use):
                raise ValueError("Invalid analyst model name")

            cfg = AnalysisConfig(run_data=run_data, analyst_model=model_to_use)
            insight_data = await services.analysis_engine.generate_insight(cfg)

            if "insights" not in run_data:
                run_data["insights"] = []
            run_data["insights"].append(insight_data)
            await services.storage.save_run(run_id, run_data)

            return services.templates.TemplateResponse(
                request,
                "partials/analysis_view.html",
                {
                    "insight": insight_data["content"],
                    "model": model_to_use,
                    "cached": False,
                    "run_id": run_id,
                    "run_data": run_data,
                },
            )
        except Exception as exc:
            logger.error("Analysis failed: %s", exc)
            return services.templates.TemplateResponse(
                request,
                "partials/analysis_error.html",
                {
                    "error_message": str(exc),
                    "model": model_to_use or "",
                    "run_id": run_id,
                },
                status_code=200,
            )

    @app.get("/api/runs/{run_id}/pdf")
    async def download_pdf_report(request: Request, run_id: str) -> StreamingResponse:
        services = _get_services(request)
        _validate_run_id(run_id)
        try:
            run_data = await services.storage.get_run(run_id)
            paradoxes = load_paradoxes(services.paradoxes_path)
            paradox = get_paradox_by_id(paradoxes, run_data["paradoxId"])
            if not paradox:
                raise HTTPException(status_code=404, detail="Paradox definition not found")

            insight = None
            if "insights" in run_data and run_data["insights"]:
                insight = run_data["insights"][-1]

            pdf_bytes = services.report_generator.generate_pdf_report(run_data, paradox, insight)
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=report_{run_id}.pdf"},
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("PDF generation failed for %s", run_id)
            raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {exc}") from exc

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
