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
        | workflow               | prompt             | path       | terms        |
        | research_and_summarize | quantum computing  | web_search | quantum      |
        | wiki_and_answer        | Guido van Rossum   | wikipedia  | Guido,Python |
        | research_and_classify  | GPT-4 release      | web_search | GPT          |

  Rule: Multi-step DAG composition
    Scenario: DAG composes multiple steps correctly
      When I run workflow "research_and_summarize" with "artificial intelligence history"
      Then the answer should be usable
      And the trace should include "web_search"
      And the trace should include "summarization" or "function_calling"

  Rule: Workflow with retrieval and answering
    Scenario: Workflow retrieves and answers based on retrieved content
      When I run workflow "wiki_and_answer" with "who created Python"
      Then the answer should be usable
      And the answer should contain at least one of "Guido,Rossum,Python"

  Rule: Error handling in workflows
    Scenario: Workflow handles missing workflow gracefully
      When I run workflow "nonexistent_workflow" with "test prompt"
      Then the answer should be usable
      And the trace should include "error" or "fallback"

  Rule: Performance under DAG execution
    Scenario: Workflow completes within reasonable time
      When I run workflow "research_and_summarize" with "machine learning"
      Then the answer should be usable
      And the response time should be under 90 seconds

  Rule: ETL pipeline workflows (Hyperautomation)
    Scenario: Workflow extracts data from web, transforms, loads to analytics
      When I run workflow "web_to_analytics" with "scrape stock prices from finance.example.com and compute daily average"
      Then the answer should be usable
      And the trace should include "playwright" or "web_fetch"
      And the trace should include "duckdb"

    Scenario: Workflow performs data cleaning and aggregation
      When I run workflow "data_pipeline" with "load sales.csv, filter region=US, calculate sum(revenue)"
      Then the answer should be usable
      And the trace should include "duckdb"

  Rule: RPA workflow patterns
    Scenario: Workflow automates form submission end-to-end
      When I run workflow "form_automation" with "fill contact form at example.com/contact with name=John, email=john@test.com, message=Hello"
      Then the answer should be usable
      And the trace should include "playwright"

    Scenario: Workflow performs UI verification
      When I run workflow "ui_test" with "navigate to example.com, verify login button exists, take screenshot"
      Then the answer should be usable
      And the trace should include "playwright"

  Rule: Cross-system integration
    Scenario: Workflow orchestrates multiple external systems
      When I run workflow "crm_export" with "search for customer data, export to CSV, generate report"
      Then the answer should be usable
      And the trace should include "duckdb" or "web_search"

  Rule: Checkpoint and recovery
    Scenario: Workflow resumes from checkpoint after tool failure
      When I run workflow "resumable_pipeline" with "step1: search AI, step2: search ML, if step2 fails use step1 result"
      Then the answer should be usable
