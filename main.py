"""
AI Strength Comparator - Main Server
App factory with startup-time service initialization.
"""

import io
import asyncio
import logging
import os
import random
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lib.ai_service import (
    AIAuthenticationError,
    AIBillingError,
    AIRateLimitError,
    AIService,
    AIServiceError,
)
from lib.analysis import AnalysisConfig, AnalysisEngine
from lib.capabilities import (
    extract_capability_text,
    get_capability_by_id,
    load_capabilities,
)
from lib.config import AppConfig
from lib.query_processor import QueryProcessor, RunConfig
from lib.reporting import ReportGenerator
from lib.storage import RunStorage, STRICT_RUN_ID_PATTERN
from lib.strength_profile import build_strength_profile, filter_capability_tests
from lib.validation import QueryRequest, StrengthProfileRequest
from lib.view_models import RunViewModel, fetch_recent_run_view_models, safe_markdown

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
    capabilities_path: Path


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


def _resolve_iterations(
    requested_iterations: Optional[int],
    max_iterations: int,
    default: int,
) -> int:
    iterations = requested_iterations if requested_iterations is not None else default
    if iterations < 1:
        raise HTTPException(status_code=400, detail="Iterations must be >= 1")
    if iterations > max_iterations:
        raise HTTPException(
            status_code=400,
            detail=f"Iterations {iterations} exceeds limit of {max_iterations}",
        )
    return iterations


async def _persist_new_run(
    storage: RunStorage,
    model_name: str,
    run_data: dict[str, Any],
    max_attempts: int = 5,
) -> str:
    for attempt in range(max_attempts):
        run_id = await storage.generate_run_id(model_name)
        run_data["runId"] = run_id
        try:
            await storage.save_run(run_id, run_data, allow_overwrite=False)
            return run_id
        except FileExistsError:
            backoff_seconds = min(0.02 * (2**attempt), 0.2) + random.uniform(0, 0.02)
            logger.warning(
                "Run ID collision detected for %s, retrying after %.3fs",
                run_id,
                backoff_seconds,
            )
            await asyncio.sleep(backoff_seconds)
            continue
    raise RuntimeError("Failed to persist run after repeated run_id collisions")


def create_app(config_override: Optional[AppConfig] = None) -> FastAPI:
    templates_dir = "templates"
    templates = _build_templates(templates_dir)
    capabilities_path = Path(__file__).parent / "capabilities.json"
    analysis_prompt_path = Path(__file__).parent / templates_dir / "analysis_prompt.txt"

    if config_override is not None:
        app_title = config_override.APP_NAME
        app_version = config_override.VERSION
        allowed_origins = [config_override.APP_BASE_URL] if config_override.APP_BASE_URL else []
    else:
        app_title = "AI Strength Comparator"
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
            capabilities_path=capabilities_path,
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
            capabilities = load_capabilities(services.capabilities_path)
        except Exception as exc:
            logger.error("Failed to load capabilities: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="Failed to load capability definitions. Please check server logs.",
            ) from exc

        recent_run_contexts = await fetch_recent_run_view_models(
            services.storage,
            capabilities,
            config.ANALYST_MODEL,
        )

        initial_pool = [item for item in capabilities if item.get("type") == "capability"]
        if not initial_pool:
            initial_pool = capabilities

        initial_capability = random.choice(initial_pool) if initial_pool else None
        initial_capability_text = ""
        if initial_capability:
            initial_capability_text = extract_capability_text(
                initial_capability.get("promptTemplate", "")
            )

        capability_categories = sorted(
            {
                str(item.get("category", "General"))
                for item in capabilities
                if item.get("type") == "capability" and str(item.get("category", "")).strip()
            }
        )

        return services.templates.TemplateResponse(
            request,
            "index.html",
            {
                "capabilities": capabilities,
                "models": config.AVAILABLE_MODELS,
                "default_model": config.DEFAULT_MODEL,
                "recent_run_contexts": recent_run_contexts,
                "initial_capability": initial_capability,
                "initial_capability_text": initial_capability_text,
                "capability_categories": capability_categories,
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

    @app.get("/api/capabilities")
    async def get_capabilities(request: Request) -> list[dict[str, Any]]:
        services = _get_services(request)
        try:
            return load_capabilities(services.capabilities_path)
        except Exception as exc:
            logger.error("Failed to read capabilities: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to read capabilities.") from exc

    @app.get("/api/fragments/capability-details")
    async def get_capability_details(request: Request, capabilityId: str) -> HTMLResponse:
        services = _get_services(request)
        try:
            capabilities = load_capabilities(services.capabilities_path)
            capability = get_capability_by_id(capabilities, capabilityId)
            if capability is None:
                return HTMLResponse("<div>Capability not found</div>", status_code=404)

            capability_text = extract_capability_text(capability.get("promptTemplate", ""))
            return services.templates.TemplateResponse(
                request,
                "partials/capability_details.html",
                {
                    "capability": capability,
                    "capability_text": capability_text,
                },
            )
        except Exception as exc:
            logger.error("Failed to get capability details: %s", exc)
            return HTMLResponse("<div>Error loading details</div>", status_code=500)

    @app.get("/api/runs")
    async def list_runs(request: Request) -> list[dict[str, Any]]:
        services = _get_services(request)
        try:
            return await services.storage.list_runs()
        except Exception as exc:
            logger.error("Failed to list runs: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to retrieve runs.") from exc

    @app.get("/api/runs/{run_id}")
    async def get_run(request: Request, run_id: str) -> dict[str, Any]:
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

    @app.post("/api/query", response_model=None)
    async def execute_query(
        request: Request,
        query_request: QueryRequest,
    ) -> dict[str, Any] | HTMLResponse:
        services = _get_services(request)
        config = services.config
        try:
            capabilities = load_capabilities(services.capabilities_path)
            capability = get_capability_by_id(capabilities, query_request.capability_id)
            if capability is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Capability '{query_request.capability_id}' not found",
                )

            req_iterations = _resolve_iterations(
                query_request.iterations,
                config.MAX_ITERATIONS,
                default=10,
            )

            run_config = RunConfig(
                modelName=query_request.model_name,
                capability=capability,
                iterations=req_iterations,
                systemPrompt=query_request.system_prompt or "",
                params=query_request.params.model_dump() if query_request.params else {},
            )

            run_data = await services.query_processor.execute_run(run_config)
            await _persist_new_run(
                services.storage,
                query_request.model_name,
                run_data,
            )

            if request.headers.get("HX-Request"):
                vm = RunViewModel.build(run_data, capability)
                vm["config_analyst_model"] = config.ANALYST_MODEL
                return services.templates.TemplateResponse(
                    request,
                    "partials/result_item.html",
                    {"ctx": vm},
                )

            return run_data
        except HTTPException:
            raise
        except AIAuthenticationError as exc:
            raise HTTPException(status_code=401, detail="Invalid API key or unauthorized.") from exc
        except AIRateLimitError as exc:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try fewer iterations.") from exc
        except AIBillingError as exc:
            raise HTTPException(status_code=402, detail="Insufficient API credits.") from exc
        except AIServiceError as exc:
            logger.error("Query execution failed: %s", exc)
            raise HTTPException(status_code=500, detail="Internal server error") from exc
        except Exception as exc:
            logger.error("Query execution failed: %s", exc)
            raise HTTPException(status_code=500, detail="Internal server error") from exc

    @app.post("/api/profile", response_model=None)
    async def execute_profile(
        request: Request,
        profile_request: StrengthProfileRequest,
    ) -> dict[str, Any] | HTMLResponse:
        services = _get_services(request)
        config = services.config
        try:
            capabilities = load_capabilities(services.capabilities_path)
            available_categories = sorted(
                {
                    str(item.get("category", "General"))
                    for item in capabilities
                    if item.get("type") == "capability" and str(item.get("category", "")).strip()
                }
            )
            if profile_request.categories:
                valid_categories = {category.lower(): category for category in available_categories}
                invalid_categories = sorted(
                    {
                        category
                        for category in profile_request.categories
                        if category.lower() not in valid_categories
                    }
                )
                if invalid_categories:
                    invalid_csv = ", ".join(invalid_categories)
                    valid_csv = ", ".join(available_categories) or "none"
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Invalid categories: {invalid_csv}. "
                            f"Valid categories: {valid_csv}."
                        ),
                    )

            selected_capabilities = filter_capability_tests(
                capabilities,
                profile_request.categories,
            )
            if not selected_capabilities:
                raise HTTPException(
                    status_code=400,
                    detail="No capability tests found for the selected filters.",
                )

            req_iterations = _resolve_iterations(
                profile_request.iterations,
                config.MAX_ITERATIONS,
                default=1,
            )

            capability_concurrency = max(1, min(config.AI_CONCURRENCY_LIMIT, len(selected_capabilities)))
            capability_semaphore = asyncio.Semaphore(capability_concurrency)

            async def run_profile_capability(capability: dict[str, Any]) -> dict[str, Any]:
                async with capability_semaphore:
                    run_config = RunConfig(
                        modelName=profile_request.model_name,
                        capability=capability,
                        iterations=req_iterations,
                        systemPrompt=profile_request.system_prompt or "",
                        params=profile_request.params.model_dump() if profile_request.params else {},
                    )
                    run_data = await services.query_processor.execute_run(run_config)
                    await _persist_new_run(
                        services.storage,
                        profile_request.model_name,
                        run_data,
                    )
                    return run_data

            tasks = [run_profile_capability(capability) for capability in selected_capabilities]
            run_results = await asyncio.gather(*tasks, return_exceptions=True)
            runs: list[dict[str, Any]] = []
            errors: list[dict[str, str]] = []
            for capability, run_result in zip(selected_capabilities, run_results):
                if isinstance(run_result, Exception):
                    error_message = str(run_result).strip() or "Unknown error"
                    error_info = {
                        "capabilityId": str(capability.get("id", "unknown")),
                        "errorType": type(run_result).__name__,
                        "message": error_message,
                    }
                    logger.error(
                        "Profile capability run failed for %s: %s",
                        capability.get("id"),
                        run_result,
                    )
                    errors.append(error_info)
                    continue
                runs.append(run_result)

            if not runs:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "All capability runs failed.",
                        "errors": errors,
                    },
                )

            profile = build_strength_profile(
                model_name=profile_request.model_name,
                runs=runs,
                capabilities=selected_capabilities,
            )
            partial = bool(errors)

            if request.headers.get("HX-Request"):
                return services.templates.TemplateResponse(
                    request,
                    "partials/profile_item.html",
                    {
                        "profile": profile,
                        "partial": partial,
                        "errors": errors,
                    },
                )

            return {
                "profile": profile,
                "runs": runs,
                "partial": partial,
                "errors": errors,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Profile execution failed: %s", exc)
            raise HTTPException(status_code=500, detail="Internal server error") from exc

    @app.post("/api/runs/{run_id}/analyze")
    async def analyze_run(request: Request, run_id: str, regenerate: bool = False) -> HTMLResponse:
        services = _get_services(request)
        _validate_run_id(run_id)
        model_to_use = services.config.ANALYST_MODEL

        def render_analysis_error(error_message: str, status_code: int) -> HTMLResponse:
            return services.templates.TemplateResponse(
                request,
                "partials/analysis_error.html",
                {
                    "error_message": error_message,
                    "model": model_to_use or "",
                    "run_id": run_id,
                },
                status_code=status_code,
            )

        try:
            form_data = await request.form()
            requested_analyst = form_data.get("analyst_model")
            if requested_analyst and not MODEL_NAME_PATTERN.match(requested_analyst):
                return render_analysis_error("Invalid model name format", status_code=400)

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
        except FileNotFoundError:
            logger.warning("Analysis target run not found: %s", run_id)
            return render_analysis_error(f"Run '{run_id}' not found", status_code=404)
        except ValueError as exc:
            logger.warning("Analysis request validation failed for %s: %s", run_id, exc)
            return render_analysis_error(str(exc), status_code=400)
        except AIRateLimitError as exc:
            logger.warning("Analysis rate-limited for %s: %s", run_id, exc)
            return render_analysis_error(
                "Rate limit exceeded. Try again with fewer requests.",
                status_code=429,
            )
        except AIBillingError as exc:
            logger.warning("Analysis billing failure for %s: %s", run_id, exc)
            return render_analysis_error("Insufficient API credits.", status_code=402)
        except AIAuthenticationError as exc:
            logger.warning("Analysis authentication failure for %s: %s", run_id, exc)
            return render_analysis_error("Invalid API key or unauthorized.", status_code=401)
        except AIServiceError as exc:
            logger.error("Analysis service failure for %s: %s", run_id, exc)
            return render_analysis_error("Analysis service error.", status_code=502)
        except Exception as exc:
            logger.error("Analysis failed: %s", exc)
            return render_analysis_error("Internal server error", status_code=500)

    @app.get("/api/runs/{run_id}/pdf")
    async def download_pdf_report(request: Request, run_id: str) -> StreamingResponse:
        services = _get_services(request)
        _validate_run_id(run_id)
        try:
            run_data = await services.storage.get_run(run_id)
            capabilities = load_capabilities(services.capabilities_path)
            capability_id = run_data.get("capabilityId")
            capability = get_capability_by_id(capabilities, str(capability_id))
            if capability is None:
                raise HTTPException(status_code=404, detail="Capability definition not found")

            insight = None
            if "insights" in run_data and run_data["insights"]:
                insight = run_data["insights"][-1]

            pdf_bytes = services.report_generator.generate_pdf_report(run_data, capability, insight)
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
            raise HTTPException(status_code=500, detail="Failed to generate PDF report.") from exc

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
