@integration @requires_llm @acceptance
Feature: Complex end-to-end assistant acceptance
  The assistant should solve realistic prompts with a deterministic harness,
  retrieval when needed, and small local language models.

  Scenario Outline: Complex prompt satisfies explicit ground-truth criteria
    Given the local LLM server is available
    When I run acceptance case "<case_id>"
    Then the acceptance case should pass

    Examples:
      | case_id           |
      | hitchhiker        |
      | gba_pokemon_first |
      | solid             |
