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

    Scenario: Identifies creator of the Linux kernel
      When I run the agent with "Who created the Linux kernel?"
      Then the answer should be usable
      And the answer should contain at least one of "linus,torvalds"

  # ──────────────────────────────────────────────────────────────────────────
  Rule: Multi-part technical explanation

    Scenario: Explains all five SOLID principles
      When I run acceptance case "solid"
      Then the acceptance case should pass
      And the answer should contain at least one of "single responsibility,single"
      And the answer should contain at least one of "open,closed"
      And the answer should contain at least one of "liskov"
      And the answer should contain at least one of "interface"
      And the answer should contain at least one of "dependency"
      And the latency should be under 180 seconds

    Scenario: Explains algorithmic complexity with correct answer
      When I run acceptance case "binary_search_complexity"
      Then the acceptance case should pass
      And the answer should contain at least one of "log,logarithm"

  # ──────────────────────────────────────────────────────────────────────────
  Rule: Multilingual support

    Scenario: Handles Portuguese technical query
      When I run acceptance case "ml_pt"
      Then the acceptance case should pass
      And the answer should contain at least one of "aprendizado,machine learning,dados"

    Scenario: Answers Portuguese definition query in usable form
      When I run the agent with "O que é inteligência artificial?"
      Then the answer should be usable
      And the answer should contain at least one of "inteligência,artificial,intelligence,aprender"

  # ──────────────────────────────────────────────────────────────────────────
  Rule: Retrieval-grounded cultural reference resolution

    Scenario: Resolves cultural reference requiring web retrieval
      When I run acceptance case "hitchhiker"
      Then the acceptance case should pass
      And the answer should contain at least one of "hitchhiker,guide,galaxy"
      And the trace should include at least one of "web_search,wikipedia"

    Scenario: Provides specific game recommendation grounded in retrieval
      When I run acceptance case "gba_pokemon_first"
      Then the acceptance case should pass
      And the answer should contain at least one of "firered,leafgreen,emerald,recommend"
      And the trace should include at least one of "web_search,wikipedia,recommendation"

  # ──────────────────────────────────────────────────────────────────────────
  Rule: Temporal and current-state queries force retrieval

    Scenario: Uses web search for temporal query
      When I run the agent with "what is the latest stable Python release?"
      Then the answer should be usable
      And the trace should include "web_search"
      And the answer should contain at least one of "3.,python 3"

  # ──────────────────────────────────────────────────────────────────────────
  Rule: Trace path and routing observability

    Scenario: Question answering intent is routed and traced correctly
      When I run acceptance case "solid"
      Then the answer should be usable
      And the trace should include "question_answering"
      And the trace should include "route"

    Scenario: Retrieval source is recorded in trace for reference queries
      When I run acceptance case "hitchhiker"
      Then the answer should be usable
      And the trace should include at least one of "web_search,wikipedia"
      And the trace should include "retrieval"

  # ──────────────────────────────────────────────────────────────────────────
  Rule: Edge cases and graceful degradation

    Scenario: Returns usable answer for ambiguous philosophical query
      When I run the agent with "what is the meaning of life?"
      Then the answer should be usable

    Scenario: Handles compound question without tool failure
      When I run the agent with "explain recursion and give a simple example"
      Then the answer should be usable
      And the answer should contain at least one of "recursion,recursive,itself,itself"
