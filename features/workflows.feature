@integration @requires_llm @workflow @dag
Feature: DAG workflow execution
  Predefined workflows should execute through the DAG runtime, follow the
  intended retrieval path, and preserve task-relevant evidence in the answer.

  Scenario Outline: Workflow execution follows the expected retrieval path
    Given the local LLM server is available
    When I run workflow "<workflow>" with "<prompt>"
    Then the answer should be usable
    And the trace should include "<path>"
    And the answer should contain at least one of "<terms>"

    Examples:
      | workflow               | prompt             | path       | terms        |
      | research_and_summarize | quantum computing  | web_search | quantum      |
      | wiki_and_answer        | Guido van Rossum   | wikipedia  | Guido,Python |
      | research_and_classify  | GPT-4 release      | web_search | GPT          |
