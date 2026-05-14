@integration @requires_llm @agent @loop
Feature: Agent loop tool use
  The explicit agent mode should use tools for multi-step prompts and synthesize
  a usable answer from the tool results.

  Background: Server availability
    Given the local LLM server is available

  Rule: Multi-step tool invocation
    Scenario Outline: Agent loop invokes stable tool paths
      When I run the agent with "<prompt>"
      Then the answer should be usable
      And the trace should include "<path>"
      And the answer should contain at least one of "<terms>"

      Examples:
        | prompt                                                      | path       | terms           |
        | search for llama.cpp and tell me what it is                | web_search | llama,inference |
        | what is the square root of 256?                            | calculator | 16              |
        | calculate 7 times 8 and tell me if the result is even or odd | calculator | 56              |

  Rule: Tool result synthesis
    Scenario: Agent synthesizes information from tool result
      When I run the agent with "search for Python tutorials and summarize the top result"
      Then the answer should be usable
      And the trace should include "web_search"
      And the answer should contain at least one of "Python,tutorial,result"

  Rule: Multiple tool sequences
    Scenario: Agent uses multiple tools in sequence
      When I run the agent with "find information about quantum computing then explain it simply"
      Then the answer should be usable
      And the trace should include at least one of "web_search,wikipedia"

  Rule: Error handling and recovery
    Scenario: Agent handles tool failure gracefully
      When I run the agent with "search for nonexistentconcept123456789"
      Then the answer should be usable
      And the trace should include "web_search"

  Rule: Performance under agent loop
    Scenario: Agent completes within reasonable time
      When I run the agent with "search for AI news"
      Then the answer should be usable
      And the response time should be under 60 seconds

  Rule: Self-correction and reflection
    Scenario: Agent retries failed tool with refined parameters
      When I run the agent with "search for xyznonexistent123456 search again for python tutorials"
      Then the answer should be usable

  Rule: Long-running workflow
    Scenario: Agent handles multi-step process with repeated search work
      When I run the agent with "do three searches: AI news, Python tutorials, quantum computing, then summarize all three"
      Then the answer should be usable
      And the trace should include "web_search"
