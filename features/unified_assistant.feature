@integration @requires_llm @assistant @routing
Feature: Unified assistant entrypoint behavior
  The default assistant entrypoint should route simple prompts deterministically
  and return useful answers while exposing the expected trace path.

  Background: Server availability
    Given the local LLM server is available

  Rule: Deterministic intent routing
    Scenario Outline: Unified assistant routes stable prompts through expected paths
      When I run the assistant with "<prompt>"
      Then the answer should be usable
      And the trace should include "<path>"
      And the answer should contain at least one of "<terms>"

      Examples:
        | prompt                                  | path               | terms          |
        | calculate 144 divided by 12             | function_calling   | 12             |
        | search for open source AI models        | function_calling   | AI,model       |
        | quem é Linus Torvalds?                  | question_answering | Linux,Torvalds |
        | Tell me about OpenAI                    | wikipedia          | OpenAI,AI      |
        | What are the latest news about OpenAI?  | web_search         | OpenAI         |

  Rule: Fallback behavior for ambiguous prompts
    Scenario: Assistant falls back to a usable answering path for ambiguous prompts
      When I run the assistant with "what is the best programming language"
      Then the answer should be usable
      And the trace should include "question_answering"

  Rule: Edge cases and validation
    Scenario: Assistant handles greeting gracefully
      When I run the assistant with "hello"
      Then the answer should be usable
      And the answer should contain at least one of "hello,hi,hey"

    Scenario: Assistant answers mathematical expressions correctly
      When I run the assistant with "what is 25 * 4"
      Then the answer should be usable
      And the answer should contain at least one of "100"

  Rule: Performance expectations
    Scenario: Assistant responds within reasonable latency
      When I run the assistant with "what is the capital of France"
      Then the answer should be usable
      And the response time should be under 30 seconds

