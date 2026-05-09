@integration @requires_llm @assistant @routing
Feature: Unified assistant entrypoint behavior
  The default assistant entrypoint should route simple prompts deterministically
  and return useful answers while exposing the expected trace path.

  Background: Server availability
    Given the local LLM server is available

  Rule: Deterministic intent routing
    Scenario Outline: Unified assistant routes simple prompts to correct handlers
      When I run the assistant with "<prompt>"
      Then the answer should be usable
      And the trace should include "<path>"
      And the answer should contain at least one of "<terms>"

      Examples:
        | prompt                                  | path               | terms          |
        | calculate 144 divided by 12             | function_calling   | 12             |
        | search for open source AI models        | function_calling   | AI,model       |
        | what is the capital of Japan?           | question_answering | Tokyo,Japan    |
        | quem é Linus Torvalds?                  | question_answering | Linux,Torvalds |
        | Tell me about OpenAI                    | wikipedia          | OpenAI,AI      |
        | What are the latest news about OpenAI?  | web_search         | OpenAI         |

  Rule: Fallback behavior for ambiguous prompts
    Scenario: Assistant falls back to LLM for ambiguous prompts
      When I run the assistant with "what is the best programming language"
      Then the answer should be usable
      And the trace should include "llm_fallback" or "question_answering"

  Rule: Multilingual support
    Scenario Outline: Assistant handles Portuguese prompts
      When I run the assistant with "<prompt>"
      Then the answer should be usable
      And the answer should contain at least one of "<terms>"

      Examples:
        | prompt                             | terms              |
        | qual é a capital da França?        | Paris,França       |
        | me conta sobre Python              | Python,linguagem   |

  Rule: Edge cases and validation
    Scenario: Assistant handles greeting gracefully
      When I run the assistant with "hello"
      Then the answer should be usable
      And the answer should contain at least one of "hello,hi,hey"

    Scenario: Assistant routes mathematical expressions
      When I run the assistant with "what is 25 * 4"
      Then the answer should be usable
      And the trace should include "calculator"
      And the answer should contain at least one of "100"

  Rule: Performance expectations
    Scenario: Assistant responds within reasonable latency
      When I run the assistant with "what is the capital of France"
      Then the answer should be usable
      And the response time should be under 30 seconds

  Rule: Data analytics routing
    Scenario: Assistant routes data queries to DuckDB tool
      When I run the assistant with "query sales data for total revenue"
      Then the answer should be usable
      And the trace should include "duckdb" or "function_calling"

  Rule: Browser automation routing
    Scenario: Assistant routes web automation to Playwright tool
      When I run the assistant with "fill the login form at example.com with user@test.com"
      Then the answer should be usable
      And the trace should include "playwright" or "function_calling"
