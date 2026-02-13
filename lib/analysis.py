"""
Analysis Module - Arsenal Module
Generates model strength/weakness insights from run data.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any, Dict, Literal, Optional

from lib.ai_service import AIService

logger = logging.getLogger(__name__)


def _extract_json_object(text: str) -> Optional[str]:
    """Extract the first valid JSON object from mixed model output."""
    decoder = json.JSONDecoder()
    for start_idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, end_idx = decoder.raw_decode(text[start_idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return text[start_idx : start_idx + end_idx]
    return None


def _is_list_of_strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_analysis_content(content: Dict[str, Any]) -> None:
    required_keys = [
        "executive_summary",
        "strengths",
        "weaknesses",
        "reliability",
        "recommendations",
    ]
    missing_keys = [key for key in required_keys if key not in content]
    if missing_keys:
        raise ValueError(f"Analysis JSON missing keys: {missing_keys}")

    executive_summary = content.get("executive_summary")
    if not isinstance(executive_summary, str) or not executive_summary.strip():
        raise ValueError("executive_summary must be a non-empty string")

    for key in ("strengths", "weaknesses", "reliability", "recommendations"):
        if not _is_list_of_strings(content.get(key)):
            raise ValueError(f"{key} must be a list of strings")


@dataclass
class AnalysisConfig:
    run_data: Dict[str, Any]
    analyst_model: str
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class AggregateAnalysisConfig:
    payload: Dict[str, Any]
    analyst_model: str
    target_type: Literal["profile", "comparison"]
    temperature: float = 0.2
    max_tokens: int = 4096


class AnalysisEngine:
    def __init__(
        self,
        ai_service: AIService,
        prompt_template_path: Optional[Path] = None,
        aggregate_prompt_template_path: Optional[Path] = None,
    ) -> None:
        self.ai_service = ai_service
        self.prompt_template_path = prompt_template_path or (
            Path(__file__).resolve().parent.parent / "templates" / "analysis_prompt.txt"
        )
        self.aggregate_prompt_template_path = aggregate_prompt_template_path or (
            Path(__file__).resolve().parent.parent / "templates" / "aggregate_analysis_prompt.txt"
        )

    def compile_run_text(self, run_data: Dict[str, Any]) -> str:
        """Compile run data into a plain-text payload for analysis."""
        capability_type = run_data.get("capabilityType", "unknown")

        text = "Run Analysis Request\n====================\n\n"
        text += f"Model: {run_data.get('modelName', 'Unknown')}\n"
        text += f"Capability ID: {run_data.get('capabilityId', 'Unknown')}\n"
        text += f"Capability Type: {capability_type}\n"
        text += "\n--- RUN DATA START ---\n"

        summary = run_data.get("summary", {})
        if isinstance(summary, dict):
            text += "\nSummary:\n"
            for key, value in summary.items():
                text += f"- {key}: {value}\n"

        responses = run_data.get("responses", [])
        if isinstance(responses, list):
            text += "\nSample Responses:\n"
            for index, response in enumerate(responses[:10]):
                if not isinstance(response, dict):
                    continue
                score = response.get("score")
                passed = response.get("passed")
                raw = str(response.get("raw", "")).strip()
                if len(raw) > 300:
                    raw = f"{raw[:300]}..."

                text += f"- Iteration {index + 1}:"
                if score is not None:
                    text += f" score={score}"
                if passed is not None:
                    text += f" passed={passed}"
                text += f"\n  Response: {raw}\n"

        text += "\n--- RUN DATA END ---\n"
        return text

    def compile_aggregate_text(
        self,
        payload: Dict[str, Any],
        target_type: Literal["profile", "comparison"],
    ) -> str:
        """Compile profile/comparison payload into concise analysis input."""
        if target_type == "profile":
            tests = payload.get("tests", [])
            categories = payload.get("categoryBreakdown", [])
            strongest = payload.get("strongestAreas", [])
            weakest = payload.get("weakestAreas", [])

            text = "Aggregate Profile Analysis Request\n=================================\n\n"
            text += f"Model: {payload.get('modelName', 'Unknown')}\n"
            text += f"Overall Score: {payload.get('overallScore', 0)}\n"
            text += f"Overall Strength: {payload.get('overallStrength', 'Unknown')}\n"
            text += f"Tests Count: {len(tests) if isinstance(tests, list) else 0}\n\n"

            if isinstance(categories, list) and categories:
                text += "Category Breakdown:\n"
                for item in categories:
                    if not isinstance(item, dict):
                        continue
                    text += (
                        f"- {item.get('category', 'Unknown')}: "
                        f"score={item.get('averageScore', 0)} "
                        f"strength={item.get('strength', 'Unknown')} "
                        f"tests={item.get('testCount', 0)}\n"
                    )
                text += "\n"

            if isinstance(strongest, list) and strongest:
                text += "Strongest Areas:\n"
                for item in strongest[:5]:
                    if not isinstance(item, dict):
                        continue
                    text += (
                        f"- {item.get('title', 'Unknown')} "
                        f"(score={item.get('averageScore', 0)}, "
                        f"passRate={item.get('passRate', 0)})\n"
                    )
                text += "\n"

            if isinstance(weakest, list) and weakest:
                text += "Weakest Areas:\n"
                for item in weakest[:5]:
                    if not isinstance(item, dict):
                        continue
                    text += (
                        f"- {item.get('title', 'Unknown')} "
                        f"(score={item.get('averageScore', 0)}, "
                        f"passRate={item.get('passRate', 0)})\n"
                    )
                text += "\n"

            return text

        rankings = payload.get("rankings", [])
        leaders = payload.get("categoryLeaders", [])
        categories = payload.get("categories", [])

        text = "Aggregate Comparison Analysis Request\n====================================\n\n"
        text += f"Models Compared: {payload.get('modelsCompared', 0)}\n"
        text += f"Tests Per Model: {payload.get('testsPerModel', 0)}\n"
        if isinstance(categories, list):
            text += f"Categories: {', '.join(str(item) for item in categories) or 'All'}\n"
        text += "\n"

        if isinstance(rankings, list) and rankings:
            text += "Rankings:\n"
            for item in rankings:
                if not isinstance(item, dict):
                    continue
                profile = item.get("profile", {})
                profile_score = 0
                if isinstance(profile, dict):
                    profile_score = profile.get("overallScore", 0)
                text += (
                    f"- Rank {item.get('rank', '?')}: {item.get('modelName', item.get('modelId', 'Unknown'))} "
                    f"(adjusted={item.get('adjustedScore', 0)}, raw={profile_score}, "
                    f"coverage={item.get('coverage', 0)}, partial={item.get('partial', False)})\n"
                )
            text += "\n"

        if isinstance(leaders, list) and leaders:
            text += "Category Leaders:\n"
            for item in leaders:
                if not isinstance(item, dict):
                    continue
                text += (
                    f"- {item.get('category', 'Unknown')}: "
                    f"{item.get('modelName', item.get('modelId', 'Unknown'))} "
                    f"(score={item.get('averageScore', 0)})\n"
                )
            text += "\n"

        return text

    @staticmethod
    def _load_prompt_template(template_path: Path, fallback_template: str) -> str:
        try:
            with open(template_path, "r", encoding="utf-8") as prompt_file:
                return prompt_file.read()
        except Exception as error:
            logger.error(
                "Failed to load analysis prompt template (%s): %s",
                template_path,
                error,
            )
            return fallback_template

    @staticmethod
    def _parse_analysis_content(raw_content: str) -> Dict[str, Any]:
        try:
            json_str = _extract_json_object(raw_content)
            if json_str:
                parsed_content = json.loads(json_str)
            else:
                clean_content = raw_content.replace("```json", "").replace("```", "").strip()
                parsed_content = json.loads(clean_content)
            if not isinstance(parsed_content, dict):
                raise ValueError("analysis output must be a JSON object")
            _validate_analysis_content(parsed_content)
            return parsed_content
        except (json.JSONDecodeError, AttributeError, ValueError) as error:
            logger.warning("Analysis JSON parsing/validation failed: %s", error)
            return {"legacy_text": raw_content}

    async def generate_insight(self, config: AnalysisConfig) -> Dict[str, Any]:
        """
        Generate insight for a run.

        Returns:
            Dict with keys: timestamp, analystModel, content
        """
        compiled_text = self.compile_run_text(config.run_data)
        meta_prompt = self._load_prompt_template(
            self.prompt_template_path,
            "Analyze this AI benchmark run:\n$data",
        )

        template = Template(meta_prompt)
        formatted_prompt = template.safe_substitute(data=compiled_text)

        raw_content = await self.ai_service.get_model_response(
            config.analyst_model,
            formatted_prompt,
            "",
            {"temperature": config.temperature, "max_tokens": config.max_tokens},
        )
        parsed_content = self._parse_analysis_content(raw_content)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analystModel": config.analyst_model,
            "content": parsed_content,
        }

    async def generate_aggregate_insight(self, config: AggregateAnalysisConfig) -> Dict[str, Any]:
        """Generate insight for a profile/comparison aggregate payload."""
        compiled_text = self.compile_aggregate_text(config.payload, config.target_type)
        meta_prompt = self._load_prompt_template(
            self.aggregate_prompt_template_path,
            (
                "Analyze this benchmark aggregate payload and return strict JSON with keys "
                "executive_summary, strengths, weaknesses, reliability, recommendations.\n\n"
                "Target: $target_type\n\n$data"
            ),
        )

        template = Template(meta_prompt)
        formatted_prompt = template.safe_substitute(
            data=compiled_text,
            target_type=config.target_type,
        )

        raw_content = await self.ai_service.get_model_response(
            config.analyst_model,
            formatted_prompt,
            "",
            {"temperature": config.temperature, "max_tokens": config.max_tokens},
        )
        parsed_content = self._parse_analysis_content(raw_content)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analystModel": config.analyst_model,
            "targetType": config.target_type,
            "content": parsed_content,
        }
