@integration @requires_llm @agent
Feature: Agent loop tool use
  The explicit agent mode should use tools for multi-step prompts and synthesize
  a usable answer from the tool result.

  Scenario Outline: Agent loop invokes the expected tool path
    Given the local LLM server is available
    When I run the agent with "<prompt>"
    Then the answer should be usable
    And the trace should include "<path>"
    And the answer should contain at least one of "<terms>"

    Examples:
      | prompt                                                       | path       | terms           |
      | search for llama.cpp and tell me what it is                   | web_search | llama,inference |
      | what is the square root of 256?                               | calculator | 16              |
      | calculate 7 times 8 and tell me if the result is even or odd  | calculator | 56              |
