"""
Paradoxes - Arsenal Module
Centralized paradox loading and validation.
Copy-paste ready, zero dependencies on project.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TypedDict, Any


class OptionDict(TypedDict):
    """Single option in N-way paradox"""
    id: int
    label: str
    description: str


class ParadoxBase(TypedDict):
    """N-way paradox schema"""
    id: str
    title: str
    promptTemplate: str
    options: List[OptionDict]


class Paradox(ParadoxBase, total=False):
    type: str
    category: str


_REQUIRED_KEYS: Tuple[str, ...] = (
    "id",
    "title",
    "promptTemplate",
    "options",
)


def _normalize_paradox(item: object) -> Optional[Paradox]:
    """Validate and normalize paradox (supports both binary and N-way schemas)"""
    if not isinstance(item, dict):
        return None

    # Validate required string fields
    id_val = item.get("id")
    title_val = item.get("title")
    prompt_val = item.get("promptTemplate")

    if not isinstance(id_val, str) or not isinstance(title_val, str) or not isinstance(prompt_val, str):
        return None

    validated_options: List[OptionDict] = []

    # Check for N-way schema (new format with options[] array)
    options_val = item.get("options")
    if options_val is not None:
        # N-way schema validation
        if not isinstance(options_val, list) or len(options_val) < 2 or len(options_val) > 4:
            return None

        # Validate each option structure
        for opt in options_val:
            if not isinstance(opt, dict):
                return None

            opt_id = opt.get("id")
            opt_label = opt.get("label")
            opt_desc = opt.get("description")

            if not isinstance(opt_id, int) or not isinstance(opt_label, str) or not isinstance(opt_desc, str):
                return None

            if opt_id < 1 or opt_id > 4:
                return None

            validated_options.append({
                "id": opt_id,
                "label": opt_label,
                "description": opt_desc
            })
    else:
        # Binary schema fallback (old format with group1Default/group2Default)
        group1 = item.get("group1Default")
        group2 = item.get("group2Default")

        if not isinstance(group1, str) or not isinstance(group2, str):
            return None

        # Convert binary to N-way format
        validated_options = [
            {"id": 1, "label": "Option 1", "description": group1},
            {"id": 2, "label": "Option 2", "description": group2}
        ]

    result: Paradox = {
        "id": id_val,
        "title": title_val,
        "promptTemplate": prompt_val,
        "options": validated_options,
    }

    # Optional fields
    type_value = item.get("type")
    if isinstance(type_value, str):
        result["type"] = type_value

    category_value = item.get("category")
    if isinstance(category_value, str):
        result["category"] = category_value

    return result


@lru_cache(maxsize=1)
def _load_paradoxes_cached(paradoxes_path: str) -> Tuple[Paradox, ...]:
    with open(paradoxes_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Paradoxes JSON must be a list.")

    normalized: List[Paradox] = []
    for item in data:
        paradox = _normalize_paradox(item)
        if paradox is None:
            raise ValueError("Invalid paradox entry in JSON.")
        normalized.append(paradox)

    return tuple(normalized)


def load_paradoxes(paradoxes_path: Path) -> List[Paradox]:
    """Load and return validated paradoxes from JSON file."""
    return list(_load_paradoxes_cached(str(paradoxes_path)))


def clear_paradox_cache() -> None:
    """Clear the LRU cache for paradox loading (dev utility)."""
    _load_paradoxes_cached.cache_clear()


def get_paradox_by_id(paradoxes: List[Paradox], paradox_id: str) -> Optional[Paradox]:
    """Safely find paradox by ID."""
    for paradox in paradoxes:
        if paradox["id"] == paradox_id:
            return paradox
    return None


def extract_scenario_text(prompt_template: str) -> str:
    """Safely extract scenario text before Instructions."""
    if not prompt_template:
        return ""

    parts = prompt_template.split("**Instructions**")
    return parts[0].strip() if parts else prompt_template.strip()
