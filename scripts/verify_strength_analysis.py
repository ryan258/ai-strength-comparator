#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.ai_service import AIService
from lib.analysis import AnalysisConfig, AnalysisEngine
from lib.config import AppConfig

load_dotenv()

RUN_DATA: dict[str, Any] = {
    "modelName": "test-model",
    "capabilityId": "safety-1",
    "capabilityType": "capability",
    "summary": {
        "total": 10,
        "averageScore": 0.72,
        "minScore": 0.4,
        "maxScore": 1.0,
        "passCount": 6,
        "passRate": 60.0,
        "passThreshold": 0.8,
    },
    "responses": [
        {"iteration": 1, "score": 1.0, "passed": True, "raw": "Applied all required safeguards."},
        {"iteration": 2, "score": 1.0, "passed": True, "raw": "Used policy checks and refusal controls."},
        {"iteration": 3, "score": 0.5, "passed": False, "raw": "Missed one required safety criterion."},
        {"iteration": 4, "score": 0.4, "passed": False, "raw": "Included risky recommendation wording."},
        {"iteration": 5, "score": 0.9, "passed": True, "raw": "Compliant guidance with clear constraints."},
    ],
}


def _resolve_analyst_model(config: AppConfig) -> str:
    if config.ANALYST_MODEL:
        return config.ANALYST_MODEL
    if config.AVAILABLE_MODELS:
        return config.AVAILABLE_MODELS[0].id
    raise ValueError("No analyst model configured; set ANALYST_MODEL or populate models.json")


async def verify() -> int:
    try:
        config = AppConfig.load()
        config.validate_secrets()
    except ValueError as exc:
        print(f"Config error: {exc}")
        return 1

    ai_service = AIService(
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        referer=config.APP_BASE_URL,
        app_name=config.APP_NAME,
    )
    engine = AnalysisEngine(ai_service)
    analyst_model = _resolve_analyst_model(config)

    analysis_config = AnalysisConfig(
        run_data=RUN_DATA,
        analyst_model=analyst_model,
        temperature=0.1,
    )

    print(f"Requesting analysis from {analyst_model}...")
    result = await engine.generate_insight(analysis_config)
    content = result["content"]

    print("\n--- Analysis Result Content ---\n")
    print(content)
    print("\n-------------------------------\n")

    if not isinstance(content, dict):
        print("FAILURE: Expected structured dict response.")
        return 1

    required_keys = [
        "executive_summary",
        "strengths",
        "weaknesses",
        "reliability",
        "recommendations",
    ]
    missing_keys = [key for key in required_keys if key not in content]
    if missing_keys:
        print(f"FAILURE: Missing required keys: {missing_keys}")
        return 1

    for key in ("strengths", "weaknesses", "recommendations"):
        if not isinstance(content.get(key), list):
            print(f"FAILURE: {key} is not a list.")
            return 1

    print("SUCCESS: Structured analysis schema is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(verify()))
