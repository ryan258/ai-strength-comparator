"""
Shared profile/comparison orchestration and capability selection helpers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal, Mapping, Optional, Protocol, Sequence

from lib.ai_service import FATAL_AI_ERROR_TYPES
from lib.capabilities import get_capability_by_id
from lib.query_processor import RunConfig
from lib.strength_profile import build_strength_profile, filter_capability_tests

# Signature: (model_name, run_data) -> persisted run_id
PersistRun = Callable[[str, dict[str, Any]], Awaitable[str]]


class QueryProcessorProtocol(Protocol):
    async def execute_run(self, config: RunConfig) -> dict[str, Any]:
        ...


def available_capability_categories(capabilities: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return sorted, unique capability categories."""
    return sorted(
        {
            str(item.get("category", "General"))
            for item in capabilities
            if item.get("type") == "capability" and str(item.get("category", "")).strip()
        }
    )


def validate_category_filters(
    requested_categories: Optional[Sequence[str]],
    available_categories: Sequence[str],
) -> None:
    """Validate requested categories against the capability catalog."""
    if not requested_categories:
        return

    valid_categories = {category.lower(): category for category in available_categories}
    invalid_categories = sorted(
        {
            category
            for category in requested_categories
            if category.lower() not in valid_categories
        }
    )
    if invalid_categories:
        invalid_csv = ", ".join(invalid_categories)
        valid_csv = ", ".join(available_categories) or "none"
        raise ValueError(
            f"Invalid categories: {invalid_csv}. Valid categories: {valid_csv}."
        )


def resolve_selected_capabilities(
    capabilities: Sequence[Mapping[str, Any]],
    categories: Optional[Sequence[str]] = None,
) -> list[Mapping[str, Any]]:
    """Validate category filters and return the matching capability tests."""
    validate_category_filters(categories, available_capability_categories(capabilities))

    selected_capabilities = list(filter_capability_tests(capabilities, categories))
    if not selected_capabilities:
        raise ValueError("No capability tests found for the selected filters.")
    return selected_capabilities


def resolve_comparison_capabilities(
    capabilities: Sequence[Mapping[str, Any]],
    comparison_scope: Literal["categories", "capability"],
    categories: Optional[Sequence[str]] = None,
    capability_id: Optional[str] = None,
) -> tuple[list[Mapping[str, Any]], Optional[Mapping[str, Any]]]:
    """Resolve comparison targets from either categories or one capability ID."""
    if comparison_scope == "capability":
        if not capability_id:
            raise ValueError("capabilityId is required for capability comparisons.")

        selected_capability = get_capability_by_id(list(capabilities), capability_id)
        if selected_capability is None:
            raise ValueError(f"Capability '{capability_id}' not found.")
        return [selected_capability], selected_capability

    return resolve_selected_capabilities(capabilities, categories), None


def resolve_model_ids_for_comparison(
    requested_models: Optional[Sequence[str]],
    configured_models: Sequence[object],
) -> list[str]:
    """
    Resolve model IDs for comparison.

    Priority:
    - explicit request models
    - configured model list
    """
    if requested_models:
        return list(requested_models)

    resolved: list[str] = []
    for model in configured_models:
        model_id = _model_field(model, "id")
        if model_id:
            resolved.append(model_id)
    return resolved


def configured_model_name_lookup(configured_models: Sequence[object]) -> dict[str, str]:
    """Build a model ID -> display name lookup from configured models."""
    lookup: dict[str, str] = {}
    for model in configured_models:
        model_id = _model_field(model, "id")
        model_name = _model_field(model, "name")
        if model_id and model_name:
            lookup[model_id] = model_name
    return lookup


def build_category_leaders(
    ranked_results: Sequence["ModelComparisonResult"],
    capabilities: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return the top-scoring model for each capability category."""
    category_leaders: list[dict[str, Any]] = []
    categories = available_capability_categories(capabilities) or ["General"]

    for category in categories:
        best: Optional[dict[str, Any]] = None
        for result in ranked_results:
            breakdown = result.profile.get("categoryBreakdown", [])
            if not isinstance(breakdown, list):
                continue

            for entry in breakdown:
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("category", "")) != category:
                    continue

                average_score = entry.get("averageScore")
                score = float(average_score) if isinstance(average_score, (float, int)) else 0.0
                candidate = {
                    "category": category,
                    "modelName": result.model_name,
                    "modelId": result.model_id,
                    "averageScore": score,
                    "strength": entry.get("strength", ""),
                }
                if best is None or score > float(best.get("averageScore", 0.0) or 0.0):
                    best = candidate

        if best is not None:
            category_leaders.append(best)

    return category_leaders


def _model_field(model: object, field_name: str) -> str:
    if isinstance(model, Mapping):
        value = model.get(field_name)
    else:
        value = getattr(model, field_name, None)
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _resolve_fatal_batch_error(errors: Sequence[Exception]) -> Optional[Exception]:
    if not errors:
        return None

    for error_type in FATAL_AI_ERROR_TYPES:
        if all(isinstance(error, error_type) for error in errors):
            return errors[0]
    return None


@dataclass(frozen=True)
class CapabilityBatchConfig:
    """Config for running one model across many capability tests."""

    model_name: str
    capabilities: Sequence[Mapping[str, Any]]
    iterations: int
    system_prompt: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ComparisonExecutionConfig:
    """Config for comparing multiple models on the same capability set."""

    model_ids: Sequence[str]
    capabilities: Sequence[Mapping[str, Any]]
    iterations: int
    categories: Sequence[str] = field(default_factory=list)
    model_names: Mapping[str, str] = field(default_factory=dict)
    system_prompt: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityExecutionError:
    """Serializable failure information for one capability run."""

    capability_id: str
    error_type: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "capabilityId": self.capability_id,
            "errorType": self.error_type,
            "message": self.message,
        }


class BenchmarkExecutionFailedError(Exception):
    """Raised when a benchmark completes with no successful runs."""

    def __init__(self, detail: str | dict[str, Any]) -> None:
        if isinstance(detail, dict):
            message = str(detail.get("message", "Benchmark execution failed."))
        else:
            message = detail
        super().__init__(message)
        self.detail = detail


@dataclass
class CapabilityBatchResult:
    """Result for one model benchmarked over many capabilities."""

    model_name: str
    runs: list[dict[str, Any]]
    errors: list[CapabilityExecutionError]
    fatal_error: Optional[Exception] = None

    @property
    def partial(self) -> bool:
        return bool(self.errors)


@dataclass(frozen=True)
class ProfileExecutionResult:
    """Structured result for a strength-profile request."""

    profile: dict[str, Any]
    runs: list[dict[str, Any]]
    errors: list[dict[str, str]]

    @property
    def partial(self) -> bool:
        return bool(self.errors)


@dataclass
class ModelComparisonResult:
    """Structured comparison data for one model."""

    model_id: str
    model_name: str
    profile: dict[str, Any]
    errors: list[dict[str, str]]
    coverage: float
    adjusted_score: float
    tests_run: int
    tests_total: int
    fatal_error: Optional[Exception] = None
    rank: int = 0

    @property
    def partial(self) -> bool:
        return bool(self.errors)

    def as_dict(self) -> dict[str, Any]:
        return {
            "modelId": self.model_id,
            "modelName": self.model_name,
            "profile": self.profile,
            "partial": self.partial,
            "errors": self.errors,
            "coverage": self.coverage,
            "adjustedScore": self.adjusted_score,
            "testsRun": self.tests_run,
            "testsTotal": self.tests_total,
            "rank": self.rank,
        }


class BenchmarkOrchestrator:
    """Runs multi-capability profiles and multi-model comparisons."""

    def __init__(
        self,
        query_processor: QueryProcessorProtocol,
        persist_run: PersistRun,
        concurrency_limit: int,
    ) -> None:
        self.query_processor = query_processor
        self.persist_run = persist_run
        self.concurrency_limit = max(1, concurrency_limit)

    async def execute_capability_batch(
        self,
        config: CapabilityBatchConfig,
        capability_semaphore: Optional[asyncio.Semaphore] = None,
        raise_on_all_fatal: bool = True,
    ) -> CapabilityBatchResult:
        """Execute one model across many capabilities."""
        if not config.capabilities:
            return CapabilityBatchResult(model_name=config.model_name, runs=[], errors=[])

        semaphore = capability_semaphore or asyncio.Semaphore(
            max(1, min(self.concurrency_limit, len(config.capabilities)))
        )

        async def run_capability(capability: Mapping[str, Any]) -> dict[str, Any]:
            async with semaphore:
                run_config = RunConfig(
                    modelName=config.model_name,
                    capability=dict(capability),
                    iterations=config.iterations,
                    systemPrompt=config.system_prompt,
                    params=dict(config.params),
                )
                run_data = await self.query_processor.execute_run(run_config)
                await self.persist_run(config.model_name, run_data)
                return run_data

        tasks = [run_capability(capability) for capability in config.capabilities]
        run_results = await asyncio.gather(*tasks, return_exceptions=True)

        runs: list[dict[str, Any]] = []
        errors: list[CapabilityExecutionError] = []
        raw_errors: list[Exception] = []
        for capability, run_result in zip(config.capabilities, run_results):
            if isinstance(run_result, Exception):
                raw_errors.append(run_result)
                error_message = str(run_result).strip() or "Unknown error"
                errors.append(
                    CapabilityExecutionError(
                        capability_id=str(capability.get("id", "unknown")),
                        error_type=type(run_result).__name__,
                        message=error_message,
                    )
                )
                continue
            runs.append(run_result)

        fatal_error: Optional[Exception] = None
        if raw_errors and not runs:
            fatal_error = _resolve_fatal_batch_error(raw_errors)
        if fatal_error is not None and raise_on_all_fatal:
            raise fatal_error

        return CapabilityBatchResult(
            model_name=config.model_name,
            runs=runs,
            errors=errors,
            fatal_error=fatal_error,
        )

    async def execute_profile(self, config: CapabilityBatchConfig) -> ProfileExecutionResult:
        """Execute and aggregate a model strength profile."""
        batch_result = await self.execute_capability_batch(config, raise_on_all_fatal=True)
        if not batch_result.runs:
            raise BenchmarkExecutionFailedError(
                {
                    "message": "All capability runs failed.",
                    "errors": [error.as_dict() for error in batch_result.errors],
                }
            )

        profile = build_strength_profile(
            model_name=config.model_name,
            runs=batch_result.runs,
            capabilities=config.capabilities,
        )
        return ProfileExecutionResult(
            profile=profile,
            runs=batch_result.runs,
            errors=[error.as_dict() for error in batch_result.errors],
        )

    async def execute_model_comparison(
        self,
        config: ComparisonExecutionConfig,
    ) -> dict[str, Any]:
        """Execute a parallel multi-model comparison payload."""
        total_tests = len(config.capabilities)
        # Share one semaphore across all models so comparisons respect the
        # app-wide AI concurrency limit instead of multiplying it per model.
        shared_capability_semaphore = asyncio.Semaphore(self.concurrency_limit)

        async def run_model(model_id: str) -> ModelComparisonResult:
            batch_result = await self.execute_capability_batch(
                CapabilityBatchConfig(
                    model_name=model_id,
                    capabilities=config.capabilities,
                    iterations=config.iterations,
                    system_prompt=config.system_prompt,
                    params=config.params,
                ),
                capability_semaphore=shared_capability_semaphore,
                raise_on_all_fatal=False,
            )

            profile = build_strength_profile(
                model_name=model_id,
                runs=batch_result.runs,
                capabilities=config.capabilities,
            )
            coverage = (len(batch_result.runs) / total_tests) if total_tests else 0.0
            overall_score = float(profile.get("overallScore", 0.0) or 0.0)
            adjusted_score = overall_score * coverage

            return ModelComparisonResult(
                model_id=model_id,
                model_name=config.model_names.get(model_id, model_id),
                profile=profile,
                errors=[error.as_dict() for error in batch_result.errors],
                coverage=coverage,
                adjusted_score=adjusted_score,
                tests_run=len(batch_result.runs),
                tests_total=total_tests,
                fatal_error=batch_result.fatal_error,
            )

        results = await asyncio.gather(*(run_model(model_id) for model_id in config.model_ids))

        if results and all(result.tests_run == 0 for result in results):
            fatal_error = _resolve_fatal_batch_error(
                [result.fatal_error for result in results if result.fatal_error is not None]
            )
            if fatal_error is not None:
                raise fatal_error

            raise BenchmarkExecutionFailedError(
                {
                    "message": "All model comparisons failed.",
                    "errors": [
                        {
                            "modelId": result.model_id,
                            "errors": result.errors,
                        }
                        for result in results
                        if result.errors
                    ],
                }
            )

        ranked = sorted(
            results,
            key=lambda item: (
                item.adjusted_score,
                item.coverage,
                float(item.profile.get("overallScore", 0.0) or 0.0),
            ),
            reverse=True,
        )
        for index, item in enumerate(ranked, start=1):
            item.rank = index

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iterations": config.iterations,
            "categories": list(config.categories),
            "modelsCompared": len(config.model_ids),
            "testsPerModel": total_tests,
            "rankings": [item.as_dict() for item in ranked],
            "categoryLeaders": build_category_leaders(ranked, config.capabilities),
        }
