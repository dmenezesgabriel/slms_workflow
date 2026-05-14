@integration @requires_llm @acceptance
Feature: End-to-end assistant acceptance
  The assistant must solve realistic prompts end-to-end: routing, retrieval,
  grounding, and generation — all running through small local language models.

  Background: LLM server must be reachable
    Given the local LLM server is available

  # ──────────────────────────────────────────────────────────────────────────
  Rule: Factual authorship and creation questions

    Scenario: Identifies creator and release year of a well-known language
      When I run acceptance case "python_creator"
      Then the acceptance case should pass
      And the answer should contain at least one of "guido,rossum"
      And the answer should contain at least one of "1991,1989,1990"

  # ──────────────────────────────────────────────────────────────────────────
  # ──────────────────────────────────────────────────────────────────────────
  Rule: Multilingual support

    Scenario: Handles Portuguese technical query
      When I run acceptance case "ml_pt"
      Then the acceptance case should pass
      And the answer should contain at least one of "aprendizado,machine learning,dados"

  # ──────────────────────────────────────────────────────────────────────────
  Rule: Trace path and routing observability

    Scenario: Acceptance cases still expose routing and retrieval traces
      When I run acceptance case "python_creator"
      Then the answer should be usable
      And the trace should include "question_answering"
      And the trace should include at least one of "route,retrieval"
