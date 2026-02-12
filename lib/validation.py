"""
Validation - Arsenal Module
Copy-paste ready: Works in any project using Pydantic
"""

from typing import Optional, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator
import re


class GenerationParams(BaseModel):
    """Generation parameters for reproducibility"""
    temperature: float = Field(default=1.0, ge=0, le=2)
    top_p: float = Field(default=1.0, ge=0, le=1)
    max_tokens: int = Field(default=1000, ge=1, le=4000)
    seed: Optional[int] = Field(default=None, ge=0)
    frequency_penalty: float = Field(default=0, ge=0, le=2)
    presence_penalty: float = Field(default=0, ge=0, le=2)


class OptionInput(BaseModel):
    """Single option override for N-way paradoxes"""
    id: int = Field(..., ge=1, le=4, description="Option ID (1-4)")
    description: str = Field(..., max_length=1000, description="Option description text")


class OptionInputs(BaseModel):
    """Optional option overrides for trolley-type paradoxes (N-way support)"""
    options: Optional[List[OptionInput]] = Field(
        default=None,
        max_items=4,
        min_items=2,
        description="List of option overrides (2-4 options)"
    )

    @field_validator('options')
    @classmethod
    def validate_sequential_ids(cls, v: Optional[List[OptionInput]]) -> Optional[List[OptionInput]]:
        """Ensure option IDs are sequential starting from 1"""
        if v:
            ids = sorted([opt.id for opt in v])
            expected = list(range(1, len(ids) + 1))
            if ids != expected:
                raise ValueError(f'Option IDs must be sequential starting from 1. Got {ids}, expected {expected}')
        return v


class QueryRequest(BaseModel):
    """Experimental run request"""
    model_name: str = Field(..., alias="modelName", min_length=1, max_length=200)
    paradox_id: str = Field(..., alias="paradoxId", min_length=1, max_length=100)
    option_overrides: Optional[OptionInputs] = Field(default=None, alias="optionOverrides")
    iterations: Optional[int] = Field(default=10, ge=1, le=1000)
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt", max_length=2000)
    params: Optional[GenerationParams] = None

    class Config:
        populate_by_name = True

    @field_validator('model_name')
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if not re.match(r'^[a-z0-9\-_/:.]+$', v, re.IGNORECASE):
            raise ValueError('Invalid model name format')
        return v

    @field_validator('paradox_id')
    @classmethod
    def validate_paradox_id(cls, v: str) -> str:
        if not re.match(r'^[a-z0-9_-]+$', v, re.IGNORECASE):
            raise ValueError('Invalid paradox ID format')
        return v

    @model_validator(mode='before')
    @classmethod
    def parse_flat_form_data(cls, data: Any) -> Any:
        # If data is a dict (like from JSON body), check for flattened keys
        if isinstance(data, dict):
            new_data = data.copy()
            params = new_data.get('params', {})
            option_overrides = new_data.get('optionOverrides', {})

            # Helper: ensure sub-dict exists
            if not isinstance(params, dict): params = {}
            if not isinstance(option_overrides, dict): option_overrides = {}

            keys_to_remove = []
            for k, v in new_data.items():
                if k.startswith('params.'):
                    sub_key = k.split('.', 1)[1]
                    params[sub_key] = v
                    keys_to_remove.append(k)
                elif k == 'iterations' and v == '':
                    # Handle empty strings from form inputs: skip to let default apply
                    continue

            for k in keys_to_remove:
                new_data.pop(k)

            if params:
                new_data['params'] = params

            if option_overrides:
                new_data['optionOverrides'] = option_overrides

            # Type casting for form inputs (forms send strings)
            if 'iterations' in new_data and isinstance(new_data['iterations'], str):
                try:
                    new_data['iterations'] = int(new_data['iterations'])
                except ValueError:
                    pass # Pydantic will validation error later

            return new_data
        return data


class InsightRequest(BaseModel):
    """AI insight generation request"""
    runData: dict
    analystModel: Optional[str] = Field(default=None, min_length=1, max_length=200)

    @field_validator('runData')
    @classmethod
    def validate_run_data(cls, v: dict) -> dict:
        if 'responses' not in v or len(v['responses']) < 1:
            raise ValueError('runData must contain at least one response')
        return v
