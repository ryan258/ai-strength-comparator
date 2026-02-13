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
from typing import Any, Dict, Optional

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


class AnalysisEngine:
    def __init__(
        self,
        ai_service: AIService,
        prompt_template_path: Optional[Path] = None,
    ) -> None:
        self.ai_service = ai_service
        self.prompt_template_path = prompt_template_path or (
            Path(__file__).resolve().parent.parent / "templates" / "analysis_prompt.txt"
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

    async def generate_insight(self, config: AnalysisConfig) -> Dict[str, Any]:
        """
        Generate insight for a run.

        Returns:
            Dict with keys: timestamp, analystModel, content
        """
        compiled_text = self.compile_run_text(config.run_data)

        try:
            with open(self.prompt_template_path, "r", encoding="utf-8") as prompt_file:
                meta_prompt = prompt_file.read()
        except Exception as error:
            logger.error(
                "Failed to load analysis prompt template (%s): %s",
                self.prompt_template_path,
                error,
            )
            meta_prompt = "Analyze this AI benchmark run:\n{data}"

        template = Template(meta_prompt)
        formatted_prompt = template.safe_substitute(data=compiled_text)

        raw_content = await self.ai_service.get_model_response(
            config.analyst_model,
            formatted_prompt,
            "",
            {"temperature": config.temperature, "max_tokens": config.max_tokens},
        )

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

        except (json.JSONDecodeError, AttributeError, ValueError) as error:
            logger.warning("Analysis JSON parsing/validation failed: %s", error)
            parsed_content = {"legacy_text": raw_content}

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analystModel": config.analyst_model,
            "content": parsed_content,
        }
