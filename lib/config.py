"""
Configuration - Arsenal Module
Typed configuration management using Pydantic Settings
"""

import os
import json
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError

# Strict Candlelight Palette (Reference)
# Background: #121212
# Text: #EBD2BE
# Accents: #A6ACCD, #98C379, #E06C75

class ModelConfig(BaseModel):
    id: str
    name: str


def _env_bool(name: str, default: bool) -> bool:
    """Parse common boolean env formats with a strict fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"{name} must be one of: true/false, 1/0, yes/no, on/off"
    )


class AppConfig(BaseModel):
    # App Identity
    APP_NAME: str = "AI Ethics Comparator"
    VERSION: str = "6.0.0"

    # AI Service Config
    AI_CONCURRENCY_LIMIT: int = Field(default_factory=lambda: int(os.getenv("AI_CONCURRENCY_LIMIT", "2")))
    AI_MAX_RETRIES: int = Field(default_factory=lambda: int(os.getenv("AI_MAX_RETRIES", "5")))
    AI_RETRY_DELAY: int = Field(default_factory=lambda: int(os.getenv("AI_RETRY_DELAY", "2")))
    AI_CHOICE_INFERENCE_ENABLED: bool = Field(
        default_factory=lambda: _env_bool("AI_CHOICE_INFERENCE_ENABLED", True)
    )
    
    # Limits
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "20"))

    # URLs (required - no hardcoded defaults)
    APP_BASE_URL: Optional[str] = Field(default_factory=lambda: os.getenv("APP_BASE_URL"))
    OPENROUTER_BASE_URL: Optional[str] = Field(default_factory=lambda: os.getenv("OPENROUTER_BASE_URL"))

    # Secrets
    OPENROUTER_API_KEY: Optional[str] = Field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY"))

    def validate_secrets(self) -> None:
        """Validate that required environment variables are present."""
        if not self.OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY not found in environment. "
                "Please create a .env file with: OPENROUTER_API_KEY=sk-or-your-key"
            )

        if not self.APP_BASE_URL:
            raise ValueError(
                "APP_BASE_URL not found in environment. "
                "Please add to .env: APP_BASE_URL=http://localhost:8000"
            )

        if not self.OPENROUTER_BASE_URL:
            raise ValueError(
                "OPENROUTER_BASE_URL not found in environment. "
                "Please add to .env: OPENROUTER_BASE_URL=https://openrouter.ai/api/v1"
            )
    
    # Models (Loaded from env JSON or file)
    AVAILABLE_MODELS: List[ModelConfig] = Field(default_factory=list)
    ANALYST_MODEL: Optional[str] = Field(default_factory=lambda: os.getenv("ANALYST_MODEL"))
    DEFAULT_MODEL: Optional[str] = Field(default_factory=lambda: os.getenv("DEFAULT_MODEL"))

    @property
    def results_path(self) -> Path:
        return Path(__file__).parent.parent / "results"

    @classmethod
    def load(cls) -> "AppConfig":
        """Load configuration from environment and files."""
        # Initialize with env vars
        config = cls()
        
        # Load models from file if env not set
        _models_json = os.getenv("AVAILABLE_MODELS_JSON")
        if _models_json:
            try:
                data = json.loads(_models_json)
                if not isinstance(data, list):
                    raise ValueError("AVAILABLE_MODELS_JSON must be a JSON array.")
                config.AVAILABLE_MODELS = [ModelConfig(**m) for m in data]
            except json.JSONDecodeError as exc:
                raise ValueError("AVAILABLE_MODELS_JSON must be valid JSON.") from exc
            except (TypeError, ValueError) as exc:
                raise ValueError(str(exc)) from exc
            except ValidationError as exc:
                raise ValueError("AVAILABLE_MODELS_JSON contains invalid model objects.") from exc
        else:
            # Load from models.json
            models_path = Path(__file__).parent.parent / "models.json"
            if models_path.exists():
                try:
                    with open(models_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, list):
                        raise ValueError(f"{models_path.name} must contain a JSON array.")
                    config.AVAILABLE_MODELS = [ModelConfig(**m) for m in data]
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON in {models_path.name}.") from exc
                except (TypeError, ValueError) as exc:
                    raise ValueError(str(exc)) from exc
                except ValidationError as exc:
                    raise ValueError(f"Invalid model entry in {models_path.name}.") from exc

        # Smart defaults for models
        if not config.ANALYST_MODEL and config.AVAILABLE_MODELS:
            config.ANALYST_MODEL = config.AVAILABLE_MODELS[0].id
        
        if not config.DEFAULT_MODEL and config.AVAILABLE_MODELS:
            config.DEFAULT_MODEL = config.AVAILABLE_MODELS[0].id
            
        return config
