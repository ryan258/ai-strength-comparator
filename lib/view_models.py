"""
View Models - Arsenal Module
Logic-free data structures for templates.
"""

import html
import json
import logging
import re
from typing import Any, Dict, List, Optional, Protocol

import markdown
from markupsafe import Markup

from lib.strength_profile import classify_strength

logger = logging.getLogger(__name__)
MAX_RUN_JSON_PREVIEW_CHARS = 8000


class RunStorageProtocol(Protocol):
    async def list_runs(self) -> List[Dict[str, Any]]:
        ...

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        ...


def safe_markdown(text: str) -> Markup:
    """
    Render markdown safely.
    Escapes HTML first, then renders.
    """
    if not text:
        return Markup("")

    escaped = html.escape(str(text))
    rendered = markdown.markdown(escaped)

    rendered = re.sub(
        r"<a\s+[^>]*>(.*?)</a>",
        r"\1",
        rendered,
        flags=re.IGNORECASE | re.DOTALL,
    )
    rendered = re.sub(r"<img\s+[^>]*>", "", rendered, flags=re.IGNORECASE)

    return Markup(rendered)


class RunViewModel:
    """Builder for run result view data."""

    @staticmethod
    def build(run_data: Dict[str, Any], capability: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare a run record for display."""
        if not isinstance(run_data, dict):
            logger.error("Invalid run_data type: %s", type(run_data))
            return {}

        if "capabilityId" not in run_data:
            logger.warning("Run data missing capability ID")

        summary = run_data.get("summary", {})
        if not isinstance(summary, dict):
            summary = {}

        capability_type = str(run_data.get("capabilityType") or capability.get("type") or "capability")

        capability_html = safe_markdown(run_data.get("prompt", ""))

        insights = run_data.get("insights", [])
        insight_html = Markup("")
        insight_model = ""
        has_insight = False

        if isinstance(insights, list) and insights:
            latest = insights[-1]
            if isinstance(latest, dict):
                insight_content = latest.get("content", "")
                insight_model = latest.get("analystModel", "Unknown")

                if isinstance(insight_content, str):
                    insight_html = safe_markdown(insight_content)
                elif isinstance(insight_content, dict):
                    if "legacy_text" in insight_content:
                        insight_html = safe_markdown(str(insight_content["legacy_text"]))
                    else:
                        insight_html = Markup(
                            "<p><em>Analysis complete. Click 'View Analysis' to see details.</em></p>"
                        )
                else:
                    insight_html = Markup("<p><em>Invalid insight format</em></p>")

                has_insight = True

        capability_score = float(summary.get("averageScore", 0.0))
        pass_rate = float(summary.get("passRate", 0.0))
        pass_count = int(summary.get("passCount", 0))
        total_responses = summary.get("total", 0)
        if isinstance(total_responses, str):
            total_responses = 0

        strength_label = classify_strength(capability_score)
        strength_class = strength_label.lower()
        run_data_json = json.dumps(run_data, indent=2)
        run_data_json_truncated = False
        if len(run_data_json) > MAX_RUN_JSON_PREVIEW_CHARS:
            run_data_json = (
                f"{run_data_json[:MAX_RUN_JSON_PREVIEW_CHARS]}\n... (truncated for display)"
            )
            run_data_json_truncated = True

        return {
            "run_id": run_data.get("runId", "unknown"),
            "model_name": run_data.get("modelName", "Unknown"),
            "capability_title": capability.get("title", "Unknown Capability"),
            "capability_type": capability_type,
            "capability_category": capability.get("category", run_data.get("category", "General")),
            "capability_html": capability_html,
            "total_responses": total_responses,
            "capability_score": capability_score,
            "pass_rate": pass_rate,
            "pass_count": pass_count,
            "strength_label": strength_label,
            "strength_class": strength_class,
            "system_prompt": run_data.get("systemPrompt", ""),
            "has_insight": has_insight,
            "insight_html": insight_html,
            "insight_model": insight_model,
            "run_data_json": run_data_json,
            "run_data_json_truncated": run_data_json_truncated,
            "_raw_run": run_data,
        }


async def fetch_recent_run_view_models(
    storage: RunStorageProtocol,
    capabilities: List[Dict[str, Any]],
    config_analyst_model: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Fetch, sort, and build view models for recent runs.
    """
    recent_run_contexts: List[Dict[str, Any]] = []
    try:
        all_runs_meta = await storage.list_runs()

        for meta in all_runs_meta[:5]:
            try:
                run_id = meta.get("runId")
                if not run_id:
                    continue

                full_run_data = await storage.get_run(run_id)

                capability_id = full_run_data.get("capabilityId")
                capability = next(
                    (
                        item
                        for item in capabilities
                        if isinstance(item, dict) and item.get("id") == capability_id
                    ),
                    {},
                )

                vm = RunViewModel.build(full_run_data, capability)
                vm["config_analyst_model"] = config_analyst_model
                recent_run_contexts.append(vm)
            except Exception as inner_error:
                logger.warning("Failed to load run %s: %s", meta.get("runId"), inner_error)
                continue

    except Exception as error:
        logger.error("Failed to load recent runs: %s", error)

    return recent_run_contexts
