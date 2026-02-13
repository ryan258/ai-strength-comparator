"""
AI Service - Arsenal Module
OpenRouter client with retry logic and dual API support
Copy-paste ready: Just provide config
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Base exception for AI service errors."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AIAuthenticationError(AIServiceError):
    """Raised for 401 authentication failures."""


class AIBillingError(AIServiceError):
    """Raised for 402/403 billing or quota issues."""


class AIRateLimitError(AIServiceError):
    """Raised for 429 rate limit failures after retries."""


class AIModelNotFoundError(AIServiceError):
    """Raised for 404 model-not-found errors."""


class AIEmptyResponseError(AIServiceError):
    """Raised when the model returns no usable text content."""

class AIService:
    """AI Service for OpenRouter API with exponential backoff retry"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        referer: str,
        app_name: str,
        max_retries: int = 5,
        retry_delay: int = 2,
    ) -> None:
        if not api_key:
            raise ValueError("API key is required")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if retry_delay < 0:
            raise ValueError("retry_delay must be >= 0")

        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": referer,
                "X-Title": app_name
            }
        )

    @staticmethod
    def _extract_text_from_parts(parts: Any) -> str:
        """Extract text from structured content parts returned by some providers."""
        if not isinstance(parts, list):
            return ""

        extracted: List[str] = []
        for part in parts:
            if isinstance(part, str):
                text = part.strip()
                if text:
                    extracted.append(text)
                continue

            if isinstance(part, dict):
                text_value = part.get("text")
                if isinstance(text_value, str):
                    text = text_value.strip()
                    if text:
                        extracted.append(text)
                continue

            text_attr = getattr(part, "text", None)
            if isinstance(text_attr, str):
                text = text_attr.strip()
                if text:
                    extracted.append(text)

        return "\n".join(extracted)

    def _extract_response_text(self, response: Any) -> str:
        """Extract best-effort text across chat/completions provider variants."""
        choices = getattr(response, "choices", None)
        if not choices:
            return ""

        first_choice = choices[0]
        message = getattr(first_choice, "message", None)

        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text = self._extract_text_from_parts(content)
            if text:
                return text

        # Some providers populate refusal text instead of content.
        refusal = getattr(message, "refusal", None)
        if isinstance(refusal, str) and refusal.strip():
            return refusal.strip()

        # Some providers expose reasoning separately.
        reasoning = getattr(message, "reasoning", None)
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning.strip()
        if isinstance(reasoning, list):
            text = self._extract_text_from_parts(reasoning)
            if text:
                return text

        # Defensive fallback for non-chat shape.
        choice_text = getattr(first_choice, "text", None)
        if isinstance(choice_text, str) and choice_text.strip():
            return choice_text.strip()

        return ""

    @staticmethod
    def _empty_response_error(response: Any) -> str:
        """Create an actionable error when a provider returns no usable text."""
        choices = getattr(response, "choices", None)
        if not choices:
            return "Model returned no choices"

        finish_reason = getattr(choices[0], "finish_reason", None)
        if finish_reason == "length":
            return "Model hit max_tokens before yielding visible output"
        if finish_reason == "content_filter":
            return "Model response blocked by provider content filter"

        return "Model returned no usable text content"

    async def get_model_response(
        self,
        model_name: str,
        prompt: str,
        system_prompt: str = "",
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> str:
        """
        Get model response with automatic retry logic

        Args:
            model_name: Model identifier
            prompt: User prompt
            system_prompt: Optional system prompt for behavior priming
            params: Generation parameters
            retry_count: Current retry attempt (internal)

        Returns:
            Model response text
        """
        if params is None:
            params = {}

        try:
            # Build request parameters
            request_params = {
                "model": model_name,
                "temperature": params.get("temperature", 1.0),
                "top_p": params.get("top_p", 1.0),
                "max_tokens": params.get("max_tokens", 1000),
                "frequency_penalty": params.get("frequency_penalty", 0),
                "presence_penalty": params.get("presence_penalty", 0)
            }

            # Only include seed if provided
            if params.get("seed") is not None:
                request_params["seed"] = params["seed"]

            messages: List[Dict[str, str]]
            if system_prompt and system_prompt.strip():
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            else:
                messages = [{"role": "user", "content": prompt}]

            try:
                response = await self.client.chat.completions.create(
                    **request_params,
                    messages=messages
                )
            except Exception as api_error:
                if "JSON" in str(api_error):
                    logger.error("JSON parsing error - API may have returned HTML or empty response")
                    logger.error("Model: %s, Retry count: %s", model_name, retry_count)
                raise

            response_text = self._extract_response_text(response)
            if response_text:
                return response_text

            raise AIEmptyResponseError(self._empty_response_error(response))

        except Exception as error:
            return await self._handle_error(error, model_name, prompt, system_prompt, params, retry_count)

    async def _handle_error(
        self,
        error: Exception,
        model_name: str,
        prompt: str,
        system_prompt: str,
        params: Dict[str, Any],
        retry_count: int,
    ) -> str:
        """Handle errors with retry logic"""
        logger.error("Error querying OpenRouter: %s", error)

        # Re-raise our own typed errors directly.
        if isinstance(error, AIServiceError):
            raise error

        # Check for status code in error
        status_code = getattr(error, 'status_code', None)
        error_msg = str(error)

        if status_code:
            # Retry on 429 (rate limit) or 5xx (server errors)
            should_retry = (
                (status_code == 429 or status_code >= 500)
                and retry_count < self.max_retries
            )

            if should_retry:
                delay = self.retry_delay * (2 ** retry_count)
                logger.info(
                    "Retrying after %ss (attempt %s/%s)...",
                    delay,
                    retry_count + 1,
                    self.max_retries,
                )
                await asyncio.sleep(delay)
                return await self.get_model_response(model_name, prompt, system_prompt, params, retry_count + 1)

            if status_code == 404:
                raise AIModelNotFoundError(error_msg, status_code=404)
            if status_code == 429:
                raise AIRateLimitError(error_msg, status_code=429)
            if status_code in (402, 403):
                raise AIBillingError(error_msg, status_code=status_code)
            if status_code == 401:
                raise AIAuthenticationError(error_msg, status_code=401)
            raise AIServiceError(error_msg, status_code=status_code)

        # Handle network errors
        if "JSON" in error_msg or "Connection" in error_msg:
            should_retry = retry_count < self.max_retries
            if should_retry:
                delay = self.retry_delay * (2 ** retry_count)
                logger.info(
                    "Network error - retrying after %ss (attempt %s/%s)...",
                    delay,
                    retry_count + 1,
                    self.max_retries,
                )
                await asyncio.sleep(delay)
                return await self.get_model_response(model_name, prompt, system_prompt, params, retry_count + 1)

            raise AIServiceError(
                f"API error after {self.max_retries} retries: {error_msg}"
            )

        # Preserve explicit model-output failures without wrapping.
        if isinstance(error, AIEmptyResponseError):
            raise error

        raise AIServiceError(f"Failed to retrieve response: {error_msg}")
