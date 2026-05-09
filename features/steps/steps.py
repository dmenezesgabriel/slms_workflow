"""BDD step definitions following Ports & Adapters pattern.

This module imports and wires the port interfaces:
- Infrastructure: LLM server availability
- Execution: Application pipeline execution
- Assertions: Result evaluation

Step definitions delegate to port implementations, keeping the
step logic thin and testable.
"""

from __future__ import annotations

from typing import Any

from behave import given, then, when

from features.steps import assertions, execution, infrastructure


@given("the local LLM server is available")
def step_llm_server_available(context: Any) -> None:
    infrastructure.check_server_availability(context)


@when('I run the assistant with "{prompt}"')
@when('I run the direct pipeline with "{prompt}"')
def step_run_unified_assistant(context: Any, prompt: str) -> None:
    execution.execute_unified_assistant(context, prompt)


@when('I run the agent with "{prompt}"')
def step_run_agent(context: Any, prompt: str) -> None:
    execution.execute_agent(context, prompt)


@when('I run workflow "{workflow}" with "{prompt}"')
def step_run_workflow(context: Any, workflow: str, prompt: str) -> None:
    execution.execute_workflow(context, workflow, prompt)


@when('I run acceptance case "{case_id}"')
def step_run_acceptance_case(context: Any, case_id: str) -> None:
    execution.execute_acceptance_case(context, case_id)


@then("the answer should be usable")
def step_answer_should_be_usable(context: Any) -> None:
    assertions.assert_answer_usable(context)


@then('the trace should include "{expected_path}"')
def step_trace_should_include(context: Any, expected_path: str) -> None:
    assertions.assert_trace_includes(context, expected_path)


@then('the answer should contain at least one of "{terms}"')
def step_answer_should_contain_term(context: Any, terms: str) -> None:
    assertions.assert_answer_contains_term(context, terms)


@then("the acceptance case should pass")
def step_acceptance_case_should_pass(context: Any) -> None:
    assertions.assert_acceptance_case_passes(context)


@then("the response time should be under {seconds} seconds")
def step_response_time_under(context: Any, seconds: str) -> None:
    assertions.assert_response_time_under(context, float(seconds))


@then("the latency should be under {seconds} seconds")
def step_latency_under(context: Any, seconds: str) -> None:
    assertions.assert_latency_under(context, float(seconds))


@then("the trace should include one of {paths}")
def step_trace_includes_any(context: Any, paths: str) -> None:
    path_list = [p.strip() for p in paths.split(" or ")]
    assertions.assert_trace_includes_any(context, path_list)


@then('the trace should include at least one of "{terms}"')
def step_trace_includes_any_of(context: Any, terms: str) -> None:
    term_list = [t.strip() for t in terms.split(",") if t.strip()]
    assertions.assert_trace_includes_any(context, term_list)
