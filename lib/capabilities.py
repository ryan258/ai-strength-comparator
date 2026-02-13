"""
Capabilities - Arsenal Module
Centralized capability test loading and validation.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple, TypedDict


class CapabilityEvaluation(TypedDict, total=False):
    """Rule-based evaluator config for capability tests."""

    required: List[str]
    forbidden: List[str]
    pass_threshold: float
    ignore_case: bool


class Capability(TypedDict, total=False):
    """Capability definition schema."""

    id: str
    title: str
    type: str
    category: str
    promptTemplate: str
    evaluation: CapabilityEvaluation


def _normalize_capability(item: object) -> Optional[Capability]:
    """Validate and normalize capability definitions."""
    if not isinstance(item, dict):
        return None

    capability_id = item.get("id")
    title = item.get("title")
    prompt_template = item.get("promptTemplate")
    if (
        not isinstance(capability_id, str)
        or not isinstance(title, str)
        or not isinstance(prompt_template, str)
    ):
        return None

    capability_type = item.get("type", "capability")
    if capability_type != "capability":
        return None

    evaluation = item.get("evaluation")
    if not isinstance(evaluation, dict):
        return None

    required = evaluation.get("required", [])
    forbidden = evaluation.get("forbidden", [])
    pass_threshold = evaluation.get("pass_threshold", 0.8)
    ignore_case = evaluation.get("ignore_case", False)

    if (
        not isinstance(required, list)
        or not required
        or not all(isinstance(pattern, str) and pattern.strip() for pattern in required)
    ):
        return None

    if not isinstance(forbidden, list) or not all(
        isinstance(pattern, str) and pattern.strip() for pattern in forbidden
    ):
        return None

    if not isinstance(pass_threshold, (float, int)):
        return None
    threshold = float(pass_threshold)
    if threshold <= 0 or threshold > 1:
        return None
    if not isinstance(ignore_case, bool):
        return None

    capability: Capability = {
        "id": capability_id,
        "title": title,
        "type": "capability",
        "promptTemplate": prompt_template,
        "evaluation": {
            "required": [pattern.strip() for pattern in required],
            "forbidden": [pattern.strip() for pattern in forbidden],
            "pass_threshold": threshold,
            "ignore_case": ignore_case,
        },
    }

    category = item.get("category")
    if isinstance(category, str):
        capability["category"] = category

    return capability


@lru_cache(maxsize=8)
def _load_capabilities_cached(capabilities_path: str, _mtime_ns: int) -> Tuple[Capability, ...]:
    with open(capabilities_path, "r", encoding="utf-8") as capability_file:
        data = json.load(capability_file)

    if not isinstance(data, list):
        raise ValueError("Capabilities JSON must be a list.")

    normalized: List[Capability] = []
    seen_ids: set[str] = set()
    for item in data:
        capability = _normalize_capability(item)
        if capability is None:
            raise ValueError("Invalid capability entry in JSON.")
        capability_id = capability["id"]
        if capability_id in seen_ids:
            raise ValueError(f"Duplicate capability ID in JSON: {capability_id}")
        seen_ids.add(capability_id)
        normalized.append(capability)

    return tuple(normalized)


def load_capabilities(capabilities_path: Path) -> List[Capability]:
    """Load and return validated capabilities from JSON file."""
    resolved_path = capabilities_path.resolve()
    mtime_ns = resolved_path.stat().st_mtime_ns
    return list(_load_capabilities_cached(str(resolved_path), mtime_ns))


def clear_capability_cache() -> None:
    """Clear the LRU cache for capability loading (dev utility)."""
    _load_capabilities_cached.cache_clear()


def get_capability_by_id(
    capabilities: List[Capability],
    capability_id: str,
) -> Optional[Capability]:
    """Safely find capability by ID."""
    for capability in capabilities:
        if capability["id"] == capability_id:
            return capability
    return None


def extract_capability_text(prompt_template: str) -> str:
    """Extract capability prompt text before optional instruction marker."""
    if not prompt_template:
        return ""

    parts = prompt_template.split("**Instructions**")
    return parts[0].strip() if parts else prompt_template.strip()
