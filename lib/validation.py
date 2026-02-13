"""
Validation - Arsenal Module
Pydantic request/parameter models.
"""

from typing import Any, List, Optional
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GenerationParams(BaseModel):
    """Generation parameters for reproducibility."""

    temperature: float = Field(default=1.0, ge=0, le=2)
    top_p: float = Field(default=1.0, ge=0, le=1)
    max_tokens: int = Field(default=1000, ge=1, le=4000)
    seed: Optional[int] = Field(default=None, ge=0)
    frequency_penalty: float = Field(default=0, ge=0, le=2)
    presence_penalty: float = Field(default=0, ge=0, le=2)


class QueryRequest(BaseModel):
    """Single capability test run request."""

    model_config = ConfigDict(populate_by_name=True)

    model_name: str = Field(..., alias="modelName", min_length=1, max_length=200)
    capability_id: str = Field(
        ...,
        alias="capabilityId",
        min_length=1,
        max_length=100,
    )
    iterations: Optional[int] = Field(default=10, ge=1)
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt", max_length=2000)
    params: Optional[GenerationParams] = None

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        if not re.match(r"^[a-z0-9\-_/:.]+$", value, re.IGNORECASE):
            raise ValueError("Invalid model name format")
        return value

    @field_validator("capability_id")
    @classmethod
    def validate_capability_id(cls, value: str) -> str:
        if not re.match(r"^[a-z0-9_-]+$", value, re.IGNORECASE):
            raise ValueError("Invalid capability ID format")
        return value

    @model_validator(mode="before")
    @classmethod
    def parse_flat_form_data(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        new_data = data.copy()
        params = new_data.get("params", {})

        if not isinstance(params, dict):
            params = {}

        keys_to_remove: List[str] = []
        for key, value in new_data.items():
            if key.startswith("params."):
                sub_key = key.split(".", 1)[1]
                params[sub_key] = value
                keys_to_remove.append(key)
            elif key == "iterations" and value == "":
                continue

        for key in keys_to_remove:
            new_data.pop(key, None)

        if params:
            new_data["params"] = params

        if "iterations" in new_data and isinstance(new_data["iterations"], str):
            try:
                new_data["iterations"] = int(new_data["iterations"])
            except ValueError:
                pass

        return new_data


class StrengthProfileRequest(BaseModel):
    """Multi-scenario strength profile request."""

    model_config = ConfigDict(populate_by_name=True)

    model_name: str = Field(..., alias="modelName", min_length=1, max_length=200)
    iterations: Optional[int] = Field(default=1, ge=1)
    categories: Optional[List[str]] = Field(default=None)
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt", max_length=2000)
    params: Optional[GenerationParams] = None

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        if not re.match(r"^[a-z0-9\-_/:.]+$", value, re.IGNORECASE):
            raise ValueError("Invalid model name format")
        return value

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None

        clean = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return clean or None

    @model_validator(mode="before")
    @classmethod
    def parse_form_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        parsed = data.copy()

        raw_categories = parsed.get("categories")
        if isinstance(raw_categories, str):
            categories = [item.strip() for item in raw_categories.split(",") if item.strip()]
            parsed["categories"] = categories or None

        params = parsed.get("params", {})
        if not isinstance(params, dict):
            params = {}

        keys_to_remove: List[str] = []
        for key, value in parsed.items():
            if key.startswith("params."):
                sub_key = key.split(".", 1)[1]
                params[sub_key] = value
                keys_to_remove.append(key)

        for key in keys_to_remove:
            parsed.pop(key, None)

        if params:
            parsed["params"] = params

        if "iterations" in parsed and isinstance(parsed["iterations"], str):
            try:
                parsed["iterations"] = int(parsed["iterations"])
            except ValueError:
                pass

        return parsed
