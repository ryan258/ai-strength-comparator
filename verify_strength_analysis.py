import asyncio

from dotenv import load_dotenv

load_dotenv()

from lib.config import AppConfig
from lib.ai_service import AIService
from lib.analysis import AnalysisEngine, AnalysisConfig

# Mock run data for capability scoring output
run_data = {
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

async def verify() -> None:
    # Load real config to hit real API (we need actual analysis)
    # NOTE: This requires OPENROUTER_API_KEY to be set in .env
    try:
        config = AppConfig.load()
        config.validate_secrets()
    except ValueError as e:
        print(f"Config Error: {e}")
        return

    ai_service = AIService(
        api_key=str(config.OPENROUTER_API_KEY),
        base_url=config.OPENROUTER_BASE_URL,
        referer=config.APP_BASE_URL,
        app_name=config.APP_NAME
    )

    engine = AnalysisEngine(ai_service)

    if config.ANALYST_MODEL:
        analyst_model = config.ANALYST_MODEL
    elif config.AVAILABLE_MODELS:
        analyst_model = config.AVAILABLE_MODELS[0].id
    else:
        raise ValueError("No analyst model configured; set ANALYST_MODEL or populate models.json")

    analysis_config = AnalysisConfig(
        run_data=run_data,
        analyst_model=analyst_model,
        temperature=0.1  # Low temp for deterministic formatting
    )

    print(f"Requesting analysis from {analyst_model}...")
    result = await engine.generate_insight(analysis_config)

    content = result["content"]
    print("\n--- Analysis Result Content ---\n")
    print(content)
    print("\n-------------------------------\n")

    if not isinstance(content, dict):
        print("❌ FAILURE: Expected structured dict response.")
        return

    required_keys = [
        "executive_summary",
        "strengths",
        "weaknesses",
        "reliability",
        "recommendations",
    ]
    missing_keys = [key for key in required_keys if key not in content]
    if missing_keys:
        print(f"❌ FAILURE: Missing required keys: {missing_keys}")
        return

    if not isinstance(content["strengths"], list):
        print("❌ FAILURE: strengths is not a list.")
        return

    if not isinstance(content["weaknesses"], list):
        print("❌ FAILURE: weaknesses is not a list.")
        return

    if not isinstance(content["recommendations"], list):
        print("❌ FAILURE: recommendations is not a list.")
        return

    print("✅ SUCCESS: Structured analysis schema is valid.")

if __name__ == "__main__":
    asyncio.run(verify())
