"""
Analysis Module - Arsenal Module
Handles generation of ethical insights from run data.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import json
from string import Template
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

from lib.ai_service import AIService

@dataclass
class AnalysisConfig:
    run_data: Dict[str, Any]
    analyst_model: str
    temperature: float = 0.5
    max_tokens: int = 4096  # Increased to support detailed list outputs

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
        """Compile run data into a text format for the analyst"""
        paradox_type = run_data.get("paradoxType", "trolley")
        if paradox_type != "trolley":
            raise ValueError(f"Unsupported paradox type for analysis: {paradox_type}")

        responses = run_data.get("responses", [])
        
        text = f"Run Analysis Request\n====================\n\n"
        text += f"Model: {run_data.get('modelName', 'Unknown')}\n"
        text += f"Paradox: {run_data.get('paradoxId', 'Unknown')}\n"
        text += "\n--- RUN DATA START ---\n"
        
        summary = run_data.get("summary", {})
        text += f"\nSummary:\n"

        # Handle both N-way (options array) and legacy binary (group1/group2) schemas
        if "options" in summary:
            # N-way schema: options is a list of {id, count, percentage}
            options_meta = run_data.get("options", [])
            for opt_stat in summary["options"]:
                opt_id = opt_stat.get("id", "?")
                count = opt_stat.get("count", 0)
                # Find label from options metadata
                label = f"Option {opt_id}"
                for opt_meta in options_meta:
                    if opt_meta.get("id") == opt_id:
                        label = opt_meta.get("label", label)
                        break
                text += f"- {label}: {count}\n"
        else:
            # Legacy binary schema: group1/group2 dicts
            text += f"- Group 1: {summary.get('group1', {}).get('count', 0)}\n"
            text += f"- Group 2: {summary.get('group2', {}).get('count', 0)}\n"

        # Include undecided count if present
        undecided = summary.get("undecided", {})
        if undecided.get("count", 0) > 0:
            text += f"- Undecided: {undecided.get('count', 0)}\n"
        
        text += "\nIteration Explanations:\n"
        for idx, response in enumerate(responses):
            if not isinstance(response, dict):
                logger.warning(f"Response {idx} is not a dict: {type(response)}")
                continue
            decision = response.get('decisionToken', 'N/A')
            explanation = response.get('explanation', '')
            text += f"Iteration {idx + 1} ({decision}): {explanation}\n"
        
        text += "\n--- RUN DATA END ---\n"
        return text

    async def generate_insight(self, config: AnalysisConfig) -> Dict[str, Any]:
        """
        Generate insight for a run
        
        Returns:
             Dict with keys: timestamp, analystModel, content
        """
        compiled_text = self.compile_run_text(config.run_data)
        
        # Load prompt from template file
        try:
            with open(self.prompt_template_path, "r", encoding="utf-8") as f:
                meta_prompt = f.read()
        except Exception as e:
            logger.error("Failed to load analysis prompt template (%s): %s", self.prompt_template_path, e)
            # Fallback (minimal)
            meta_prompt = "Analyze this AI run:\n{data}"
            
        # Use string.Template for safer substitution (Code Review Fix #9)
        template = Template(meta_prompt)
        formatted_prompt = template.safe_substitute(data=compiled_text)
        
        raw_content = await self.ai_service.get_model_response(
            config.analyst_model,
            formatted_prompt,
            "",
            {"temperature": config.temperature, "max_tokens": config.max_tokens}
        )

        # Try to parse as JSON (New Dashboard)
        try:
            # Enhanced JSON extraction (balanced brace counting) suggested by review
            def extract_json_object(text: str) -> Optional[str]:
                """Extract first complete JSON object from text."""
                brace_count = 0
                start_idx = text.find('{')
                if start_idx == -1: return None

                for i, char in enumerate(text[start_idx:], start=start_idx):
                    if char == '{': brace_count += 1
                    elif char == '}': 
                        brace_count -= 1
                        if brace_count == 0: return text[start_idx:i+1]
                return None

            json_str = extract_json_object(raw_content)
            
            if json_str:
                parsed_content = json.loads(json_str)
            else:
                # Try fallback cleaning
                clean_content = raw_content.replace('```json', '').replace('```', '').strip()
                parsed_content = json.loads(clean_content)

            # JSON Schema Validation (Critical Issue #3)
            required_keys = ["dominant_framework", "moral_complexes", "justifications", "consistency", "key_insights"]
            missing_keys = [k for k in required_keys if k not in parsed_content]
            
            if missing_keys:
                logger.warning(f"JSON missing keys: {missing_keys}")
                # Fall back to legacy if critical keys hidden, or keep partial?
                # Review says "Invalid JSON structure causes errors", so fallback is safer
                parsed_content = {"legacy_text": raw_content}
            else:
                 # Validate types
                 if not isinstance(parsed_content.get("moral_complexes"), list):
                     raise ValueError("moral_complexes must be list")
                 if not isinstance(parsed_content.get("key_insights"), list):
                     raise ValueError("key_insights must be list")

        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            logger.warning(f"JSON parsing/validation failed: {e}")
            # Fallback to legacy text format
            parsed_content = {"legacy_text": raw_content}
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analystModel": config.analyst_model,
            "content": parsed_content
        }
