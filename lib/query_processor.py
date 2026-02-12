"""
Query Processor - Arsenal Module
Executes experimental runs with paradox-aware response parsing
Nearly copy-paste ready: Depends on ai_service patterns
"""

import asyncio
import re
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
import logging
from lib.ai_service import AIService

logger = logging.getLogger(__name__)


def _decision_tokens(option_count: int) -> List[str]:
    """Return canonical decision tokens for the current option count."""
    return [f"{{{i}}}" for i in range(1, option_count + 1)]


def _strict_single_choice_contract(option_count: int) -> str:
    """Build a strict output contract to enforce one decision token."""
    tokens = _decision_tokens(option_count)
    token_list = ", ".join(f"`{token}`" for token in tokens)
    return (
        "\n\n**Output Contract (Strict):**\n\n"
        f"- Choose exactly one decision token from: {token_list}.\n"
        "- The first non-whitespace characters of your response MUST be that single token.\n"
        "- Do not include any other decision token anywhere in your response.\n"
        "- Do not write token alternatives such as \"{1} or {2}\".\n"
        "- After the token, provide your reasoning."
    )


def _extract_choice_from_classifier_output(classifier_output: str, option_count: int) -> Optional[int]:
    """Extract a single option ID from classifier output; 0 means undecided."""
    if option_count < 1:
        return None

    pattern = r"\b([0-" + str(option_count) + r"])\b"
    numeric_match = re.search(pattern, classifier_output)
    if numeric_match:
        value = int(numeric_match.group(1))
        if value == 0:
            return None
        return value

    brace_pattern = r"\{([1-" + str(option_count) + r"])\}"
    brace_match = re.search(brace_pattern, classifier_output)
    if brace_match:
        return int(brace_match.group(1))

    return None


def _infer_option_from_text(response_text: str, option_count: int) -> Optional[int]:
    """
    Infer a final option choice from natural-language commitment phrases.
    Returns None when no clear single commitment is present.
    """
    if not response_text or option_count < 1:
        return None

    explicit_patterns = [
        (
            r"(?i)\b(?:i|we)\s+(?:choose|chose|select|selected|recommend|recommended|pick|picked|prefer|support)\b"
            r"[^0-9{}]{0,40}(?:option|policy|choice)?\s*\{?([1-" + str(option_count) + r"])\}?"
        ),
        (
            r"(?i)\b(?:i(?:'d| would)\s+(?:choose|select|recommend|pick|go with)|i\s+will\s+(?:choose|select|recommend|pick))\b"
            r"[^0-9{}]{0,40}(?:option|policy|choice)?\s*\{?([1-" + str(option_count) + r"])\}?"
        ),
        (
            r"(?i)\b(?:my|the)\s+(?:choice|recommendation)\s+(?:is|:)\s*(?:option|policy|choice)?\s*\{?([1-"
            + str(option_count)
            + r"])\}?"
        ),
    ]

    inferred: List[int] = []
    for pattern in explicit_patterns:
        inferred.extend(int(m) for m in re.findall(pattern, response_text))

    if not inferred:
        return None

    unique_ids = set(inferred)
    if len(unique_ids) == 1:
        return inferred[-1]

    return None


def _build_choice_inference_prompt(response_text: str, option_count: int) -> str:
    """
    Build a strict extraction prompt for AI fallback when parser+heuristics fail.
    Returns only the classifier instruction text.
    """
    if len(response_text) > 6000:
        response_text = f"{response_text[:3000]}\n\n...[truncated]...\n\n{response_text[-3000:]}"

    return (
        "Classify the FINAL chosen option in the following model response.\n"
        f"Valid options are integers 1..{option_count}.\n"
        "Return exactly one character only:\n"
        f"- '1'..'{option_count}' if there is one clear final choice\n"
        "- '0' if no clear single final choice exists\n"
        "Rules:\n"
        "- Ignore option lists and hypothetical analysis.\n"
        "- Use only an explicit final commitment (e.g. \"I choose option 2\", \"I'd pick {3}\").\n"
        "- If the text contains conflicting commitments, return 0.\n"
        "- Do not output any words.\n\n"
        "MODEL RESPONSE START\n"
        f"{response_text}\n"
        "MODEL RESPONSE END"
    )


def render_options_template(
    paradox: Dict[str, Any],
    overrides: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Render N-way options into prompt template

    Args:
        paradox: Paradox definition with options[] array
        overrides: Optional list of {id, description} overrides

    Returns:
        Tuple of (rendered_prompt, resolved_options)
    """
    options = paradox.get("options", [])

    # Apply overrides if provided
    if overrides:
        override_map = {opt["id"]: opt["description"] for opt in overrides}
        options = [
            {**opt, "description": override_map.get(opt["id"], opt["description"])}
            for opt in options
        ]

    template = paradox["promptTemplate"]

    # Support both {{OPTIONS}} (new) and {{GROUP1}}/{{GROUP2}} (legacy) placeholders
    if "{{OPTIONS}}" in template:
        # New N-way format: Build numbered list
        options_text = "\n\n".join([
            f'{opt["id"]}. **{opt["label"]}:** {opt["description"]}'
            for opt in options
        ])
        prompt = template.replace("{{OPTIONS}}", options_text)
    else:
        # Legacy binary format: Replace GROUP1/GROUP2 individually
        prompt = template
        if len(options) >= 1:
            prompt = prompt.replace("{{GROUP1}}", options[0]["description"])
        if len(options) >= 2:
            prompt = prompt.replace("{{GROUP2}}", options[1]["description"])

    if options:
        prompt = f"{prompt}{_strict_single_choice_contract(len(options))}"

    return prompt, options


def parse_trolley_response(response_text: str, option_count: int) -> Dict[str, Any]:
    """
    Parse trolley-type response for decision tokens (N-way support)

    Args:
        response_text: Raw AI response text
        option_count: Number of options (2-4)

    Returns:
        Dict with decisionToken, optionId (int), and explanation
    """
    # Dynamic regex based on option count: {1} through {N}
    pattern = r'\{([1-' + str(option_count) + r'])\}'
    matches = re.findall(pattern, response_text)

    if not matches:
        return {
            "decisionToken": None,
            "optionId": None,
            "explanation": response_text.strip()
        }

    unique_matches = set(matches)
    if len(unique_matches) > 1:
        logger.warning("Ambiguous response with multiple decision tokens: %s", matches)
        return {
            "decisionToken": None,
            "optionId": None,
            "explanation": response_text.strip()
        }

    decision_token = "{" + matches[0] + "}"
    option_id = int(matches[0])  # Convert to integer

    # Extract explanation after decision token
    match = re.search(pattern, response_text)
    explanation = response_text[match.end():].strip()

    return {
        "decisionToken": decision_token,
        "optionId": option_id,  # Integer instead of string
        "explanation": explanation
    }


def aggregate_trolley_stats(responses: List[Dict[str, Any]], option_count: int) -> Dict[str, Any]:
    """
    Aggregate N-way trolley statistics

    Args:
        responses: List of response dictionaries
        option_count: Number of options (2-4)

    Returns:
        Summary dict with dynamic options[] array and undecided count
    """
    total = len(responses)

    # Initialize counters for each option
    option_counts = {i: 0 for i in range(1, option_count + 1)}
    undecided_count = 0

    # Count responses
    for r in responses:
        option_id = r.get("optionId")
        if option_id and 1 <= option_id <= option_count:
            option_counts[option_id] += 1
        else:
            undecided_count += 1

    # Build dynamic summary
    return {
        "total": total,
        "options": [
            {
                "id": i,
                "count": option_counts[i],
                "percentage": (option_counts[i] / total * 100) if total > 0 else 0
            }
            for i in range(1, option_count + 1)
        ],
        "undecided": {
            "count": undecided_count,
            "percentage": (undecided_count / total * 100) if total > 0 else 0
        }
    }


from dataclasses import dataclass, field

@dataclass
class RunConfig:
    """Configuration for an experimental run (N-way support)"""
    modelName: str
    paradox: Dict[str, Any]
    option_overrides: Optional[List[Dict[str, Any]]] = None
    iterations: int = 10
    systemPrompt: str = ""
    params: Dict[str, Any] = field(default_factory=dict)




class QueryProcessor:
    """
    Query Processor
    Manages concurrent iteration execution with paradox-aware parsing
    """

    def __init__(
        self,
        ai_service: AIService,
        concurrency_limit: int = 2,
        choice_inference_model: Optional[str] = None,
    ) -> None:
        self.ai_service = ai_service
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.choice_inference_model = choice_inference_model

    async def _infer_option_id_with_fallback(
        self,
        response_text: str,
        option_count: int,
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        Infer an option ID when strict token parsing fails.
        Returns (option_id, method) where method is 'heuristic' or 'ai_classifier'.
        """
        heuristic_option = _infer_option_from_text(response_text, option_count)
        if heuristic_option is not None:
            return heuristic_option, "heuristic"

        if not self.choice_inference_model:
            return None, None

        classifier_prompt = _build_choice_inference_prompt(response_text, option_count)
        classifier_output = await self.ai_service.get_model_response(
            self.choice_inference_model,
            classifier_prompt,
            "",
            {"temperature": 0, "top_p": 1, "max_tokens": 4},
        )
        inferred_option = _extract_choice_from_classifier_output(classifier_output, option_count)
        if inferred_option is None:
            return None, None
        return inferred_option, "ai_classifier"

    async def execute_run(self, config: RunConfig) -> Dict[str, Any]:
        """
        Execute experimental run
        
        Args:
            config: Explicit RunConfig object
            
        Returns:
            Complete run data with responses and summary
        """
        model_name = config.modelName
        paradox = config.paradox
        option_overrides = config.option_overrides
        iterations = config.iterations
        system_prompt = config.systemPrompt
        params = config.params

        paradox_type = paradox.get("type")
        if paradox_type != "trolley":
            raise ValueError(f"Unsupported paradox type: {paradox_type}")

        # Use render_options_template for N-way support.
        prompt, resolved_options = render_options_template(paradox, option_overrides)
        option_count = len(resolved_options)

        if system_prompt:
            prompt = f"PERSONA: {system_prompt}\n\n{prompt}"
        
        # Execute iterations with concurrency limiting
        async def run_iteration(iteration_number: int):
            async with self.semaphore:
                response = await self.ai_service.get_model_response(
                    model_name,
                    prompt,
                    "", # Pass empty string to disable system prompt handling in AI service
                    params
                )

                timestamp = datetime.now(timezone.utc).isoformat()

                # Parse with N-way support.
                parsed = parse_trolley_response(response, option_count)
                inferred = False
                inference_method: Optional[str] = None

                if parsed["optionId"] is None:
                    try:
                        inferred_option, inference_method = await self._infer_option_id_with_fallback(
                            response,
                            option_count,
                        )
                    except Exception as inference_error:
                        logger.warning("Choice inference fallback failed: %s", inference_error)
                        inferred_option, inference_method = None, None

                    if inferred_option is not None:
                        parsed["decisionToken"] = f"{{{inferred_option}}}"
                        parsed["optionId"] = inferred_option
                        inferred = True

                result = {
                    "iteration": iteration_number,
                    "decisionToken": parsed["decisionToken"],
                    "optionId": parsed["optionId"],
                    "explanation": parsed["explanation"],
                    "raw": response,
                    "timestamp": timestamp
                }
                if inferred and inference_method:
                    result["inferred"] = True
                    result["inferenceMethod"] = inference_method
                return result

        # Run all iterations concurrently (limited by semaphore)
        tasks = [run_iteration(i + 1) for i in range(iterations)]
        
        # Add global timeout (e.g. 5 minutes) to prevent hanging forever
        timeout_seconds = 300
        try:
            responses = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
             logger.error("Query batch timed out")
             # We might want to return partial results or just fail. 
             # Implementation choice: fail hard or return error dicts. 
             # Let's fail hard to signal critical issue.
             raise Exception(f"Query executions exceeded {timeout_seconds}s timeout")
        
        # Filter out exceptions from gather results
        valid_responses = []
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                logger.error(f"Iteration {i+1} failed: {resp}")
                # Create a strict error response structure
                valid_responses.append({
                    "iteration": i+1,
                    "error": str(resp),
                    "raw": str(resp),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            else:
                valid_responses.append(resp)
                
        responses = valid_responses

        # Build run data
        run_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "modelName": model_name,
            "paradoxId": paradox["id"],
            "paradoxType": "trolley",
            "prompt": prompt,
            "iterationCount": iterations,
            "params": {
                "temperature": params.get("temperature", 1.0),
                "top_p": params.get("top_p", 1.0),
                "max_tokens": params.get("max_tokens", 1000),
                "frequency_penalty": params.get("frequency_penalty", 0),
                "presence_penalty": params.get("presence_penalty", 0)
            },
            "responses": responses
        }

        # Add optional fields
        if system_prompt:
            run_data["systemPrompt"] = system_prompt

        if params.get("seed") is not None:
            run_data["params"]["seed"] = params["seed"]

        # Store resolved options (N-way support).
        run_data["options"] = resolved_options
        run_data["summary"] = aggregate_trolley_stats(responses, option_count)

        return run_data
