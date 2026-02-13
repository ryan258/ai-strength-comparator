# North Star: AI Strength Comparator

## Mission
Build the most practical local-first tool for answering one question with evidence:

**"What is this model reliably good at, and where does it fail?"**

## Product Outcome
For any model under test, the system should produce a profile that is:

- **Actionable**: identifies strongest and weakest capability areas
- **Deterministic**: uses objective scoring rules, not subjective judgments
- **Comparable**: supports apples-to-apples runs across models and time
- **Reproducible**: same test + same params + same seed should be re-runnable

## Benchmark Philosophy
Each capability test must satisfy all of the following:

1. **Single objective**
   One task per capability test, one measurable success condition.
2. **Constrained output**
   Prompt should request a strict format (token, number, JSON, CSV, etc.).
3. **Deterministic grading**
   Scenario must include explicit `evaluation.required` and `evaluation.forbidden` patterns.
4. **Low ambiguity**
   Avoid open-ended prompts that cannot be scored reliably.
5. **Stable truth conditions**
   Prefer tasks whose ground truth does not change over time.

## Current Capability Domains
The default benchmark suite targets:

- Reasoning
- Logic
- Data Reasoning
- Instruction Following
- Extraction
- Coding
- Creativity
- Novel Ideation
- Research Grounding
- Writing
- Safety
- Reliability

## Creativity and Research Policy
- Creativity and ideation are evaluated with constrained-output novelty proxies (structure, anti-cliche constraints, mechanism + validation requirements).
- Research quality is evaluated with source-grounded tasks where outputs must match provided evidence and citation format.
- We do not treat unsupported open-world claims as passing research output.

## What Success Looks Like
A run is successful when users can:

- run one model against the full suite
- inspect pass rates and average score per capability test
- view strongest/weakest areas by category
- generate a report they can use for model selection decisions

## Non-Goals
- Not a chatbot product
- Not a generic eval framework for every possible metric
- Not a replacement for heavy external benchmark platforms

## Operating Rule
When adding features, ask first:

**Does this improve the quality, comparability, or actionability of model strength profiles?**

If no, defer it.
