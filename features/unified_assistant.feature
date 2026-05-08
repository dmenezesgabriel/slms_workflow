@integration @requires_llm @assistant
Feature: Unified assistant entrypoint behavior
  The default assistant entrypoint should route simple prompts deterministically
  and return useful answers while exposing the expected trace path.

  Scenario Outline: Unified assistant handles representative prompts
    Given the local LLM server is available
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
