"""
Query Processor - Arsenal Module
Executes deterministic capability runs with regex-based scoring.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from lib.ai_service import AIService

logger = logging.getLogger(__name__)


def _evaluation_regex_flags(evaluation: Dict[str, Any]) -> int:
    flags = re.MULTILINE
    if evaluation.get("ignore_case") is True:
        flags |= re.IGNORECASE
    return flags


def evaluate_capability_response(
    response_text: str,
    evaluation: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Deterministically score a capability-test response using regex rules.

    Score logic:
    - Base score is required_matches / required_count.
    - Each forbidden match subtracts 0.5 (floored at 0).
    - Response passes when score >= pass_threshold.
    """
    required = [
        pattern
        for pattern in evaluation.get("required", [])
        if isinstance(pattern, str) and pattern.strip()
    ]
    forbidden = [
        pattern
        for pattern in evaluation.get("forbidden", [])
        if isinstance(pattern, str) and pattern.strip()
    ]

    threshold_value = evaluation.get("pass_threshold", 0.8)
    pass_threshold = float(threshold_value) if isinstance(threshold_value, (float, int)) else 0.8

    regex_flags = _evaluation_regex_flags(evaluation)

    required_hits: list[str] = []
    missing_required: list[str] = []
    for pattern in required:
        try:
            if re.search(pattern, response_text, flags=regex_flags):
                required_hits.append(pattern)
            else:
                missing_required.append(pattern)
        except re.error:
            logger.warning("Invalid required evaluation regex: %s", pattern)
            missing_required.append(pattern)

    forbidden_hits: list[str] = []
    for pattern in forbidden:
        try:
            if re.search(pattern, response_text, flags=regex_flags):
                forbidden_hits.append(pattern)
        except re.error:
            logger.warning("Invalid forbidden evaluation regex: %s", pattern)

    base_score = (len(required_hits) / len(required)) if required else 1.0
    penalty = 0.5 * len(forbidden_hits)
    score = max(0.0, base_score - penalty)

    return {
        "score": score,
        "passed": score >= pass_threshold,
        "passThreshold": pass_threshold,
        "matchedRequired": required_hits,
        "missingRequired": missing_required,
        "matchedForbidden": forbidden_hits,
    }


def aggregate_capability_stats(
    responses: list[Dict[str, Any]],
    pass_threshold: float,
) -> Dict[str, Any]:
    """Aggregate pass rate and score distribution for capability runs."""
    total = len(responses)
    if total == 0:
        return {
            "total": 0,
            "averageScore": 0.0,
            "minScore": 0.0,
            "maxScore": 0.0,
            "passCount": 0,
            "passRate": 0.0,
            "passThreshold": pass_threshold,
        }

    scores: list[float] = []
    pass_count = 0
    for response in responses:
        raw_score = response.get("score", 0.0)
        score = float(raw_score) if isinstance(raw_score, (float, int)) else 0.0
        scores.append(score)

        if response.get("passed") is True:
            pass_count += 1

    average_score = sum(scores) / total

    return {
        "total": total,
        "averageScore": average_score,
        "minScore": min(scores),
        "maxScore": max(scores),
        "passCount": pass_count,
        "passRate": (pass_count / total) * 100,
        "passThreshold": pass_threshold,
    }


@dataclass
class RunConfig:
    """Configuration for one capability run."""

    modelName: str
    capability: Optional[Dict[str, Any]] = None
    iterations: int = 10
    systemPrompt: str = ""
    params: Dict[str, Any] = field(default_factory=dict)

    def resolved_capability(self) -> Dict[str, Any]:
        """Return the active capability definition."""
        if not isinstance(self.capability, dict):
            raise ValueError("RunConfig requires a capability definition")
        return self.capability


class QueryProcessor:
    """Executes concurrent deterministic capability tests."""

    def __init__(
        self,
        ai_service: AIService,
        concurrency_limit: int = 2,
    ) -> None:
        self.ai_service = ai_service
        self.semaphore = asyncio.Semaphore(concurrency_limit)

    async def _execute_capability_run(self, config: RunConfig) -> Dict[str, Any]:
        capability = config.resolved_capability()
        prompt = capability["promptTemplate"]

        if config.systemPrompt:
            prompt = f"PERSONA: {config.systemPrompt}\n\n{prompt}"

        evaluation = capability.get("evaluation", {})
        pass_threshold = float(evaluation.get("pass_threshold", 0.8))

        async def run_iteration(iteration_number: int) -> Dict[str, Any]:
            async with self.semaphore:
                response = await self.ai_service.get_model_response(
                    config.modelName,
                    prompt,
                    "",
                    config.params,
                )
                score_result = evaluate_capability_response(response, evaluation)
                return {
                    "iteration": iteration_number,
                    "raw": response,
                    "score": score_result["score"],
                    "passed": score_result["passed"],
                    "matchedRequired": score_result["matchedRequired"],
                    "missingRequired": score_result["missingRequired"],
                    "matchedForbidden": score_result["matchedForbidden"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        tasks = [run_iteration(i + 1) for i in range(config.iterations)]

        timeout_seconds = 300
        try:
            responses = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError as timeout_error:
            logger.error("Capability batch timed out")
            raise Exception(
                f"Capability test exceeded {timeout_seconds}s timeout"
            ) from timeout_error

        valid_responses: list[Dict[str, Any]] = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error("Capability iteration %s failed: %s", i + 1, response)
                valid_responses.append(
                    {
                        "iteration": i + 1,
                        "error": str(response),
                        "raw": str(response),
                        "score": 0.0,
                        "passed": False,
                        "matchedRequired": [],
                        "missingRequired": [],
                        "matchedForbidden": [],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
            else:
                valid_responses.append(response)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "modelName": config.modelName,
            "capabilityId": capability["id"],
            "capabilityType": "capability",
            "category": capability.get("category", "General"),
            "prompt": prompt,
            "systemPrompt": config.systemPrompt,
            "iterationCount": config.iterations,
            "params": config.params,
            "responses": valid_responses,
            "summary": aggregate_capability_stats(valid_responses, pass_threshold),
        }

    async def execute_run(self, config: RunConfig) -> Dict[str, Any]:
        """Execute a capability test run and return full run data."""
        if config.params is None:
            config.params = {}

        config.params = {
            "temperature": config.params.get("temperature", 1.0),
            "top_p": config.params.get("top_p", 1.0),
            "max_tokens": config.params.get("max_tokens", 1000),
            "frequency_penalty": config.params.get("frequency_penalty", 0),
            "presence_penalty": config.params.get("presence_penalty", 0),
            "seed": config.params.get("seed"),
        }
        config.params = {key: value for key, value in config.params.items() if value is not None}

        capability = config.resolved_capability()
        capability_type = capability.get("type", "capability")
        if capability_type != "capability":
            raise ValueError(f"Unsupported capability type: {capability_type}")

        return await self._execute_capability_run(config)
