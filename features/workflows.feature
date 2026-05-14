@integration @requires_llm @workflow @dag
Feature: DAG workflow execution
  Predefined workflows should execute through the DAG runtime, follow the
  intended retrieval path, and preserve task-relevant evidence in the answer.

  Background: Server availability
    Given the local LLM server is available

  Rule: Predefined workflow execution
    Scenario Outline: Workflow executes through DAG with correct path
      When I run workflow "<workflow>" with "<prompt>"
      Then the answer should be usable
      And the trace should include "<path>"
      And the answer should contain at least one of "<terms>"

      Examples:
        | workflow               | prompt            | path       | terms   |
        | research_and_summarize | quantum computing | web_search | quantum |
        | research_and_classify  | GPT-4 release     | web_search | GPT     |

  Rule: Multi-step DAG composition
    Scenario: DAG composes multiple steps correctly
      When I run workflow "research_and_summarize" with "artificial intelligence history"
      Then the answer should be usable
      And the trace should include "web_search"
      And the trace should include at least one of "summarization,function_calling"

  Rule: Performance under DAG execution
    Scenario: Workflow completes within reasonable time
      When I run workflow "research_and_summarize" with "machine learning"
      Then the answer should be usable
      And the response time should be under 90 seconds

