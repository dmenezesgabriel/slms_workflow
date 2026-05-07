@integration @requires_llm
Feature: Live SLM pipeline behavior
  Live scenarios validate user-visible behavior while eval runners keep aggregate metrics.

  Scenario Outline: Direct pipeline handles representative prompts
    Given the local LLM server is available
    When I run the direct pipeline with "<prompt>"
    Then the answer should be usable
    And the trace should include "<path>"
    And the answer should contain at least one of "<terms>"

    Examples:
      | prompt                              | path               | terms          |
      | calculate 144 divided by 12         | function_calling   | 12             |
      | search for open source AI models    | function_calling   | AI,model       |
      | what is the capital of Japan?       | question_answering | Tokyo,Japan    |
      | quem é Linus Torvalds?              | question_answering | Linux,Torvalds |
      | Tell me about OpenAI                | wikipedia          | OpenAI,AI      |
      | What are the latest news about OpenAI? | web_search       | OpenAI         |

  Scenario Outline: Workflow execution follows the expected retrieval path
    Given the local LLM server is available
    When I run workflow "<workflow>" with "<prompt>"
    Then the answer should be usable
    And the trace should include "<path>"
    And the answer should contain at least one of "<terms>"

    Examples:
      | workflow               | prompt                      | path       | terms        |
      | research_and_summarize | quantum computing           | web_search | quantum      |
      | wiki_and_answer        | Guido van Rossum            | wikipedia  | Guido,Python |
      | research_and_classify  | GPT-4 release               | web_search | GPT          |

  Scenario Outline: Agent loop invokes the expected tool path
    Given the local LLM server is available
    When I run the agent with "<prompt>"
    Then the answer should be usable
    And the trace should include "<path>"
    And the answer should contain at least one of "<terms>"

    Examples:
      | prompt                                                       | path       | terms           |
      | search for llama.cpp and tell me what it is                  | web_search | llama,inference |
      | what is the square root of 256?                               | calculator | 16              |
      | calculate 7 times 8 and tell me if the result is even or odd  | calculator | 56              |
