from __future__ import annotations

import sys
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from src.dag import DagNode, DagWorkflow, run_dag_workflow
from src.graph.base import WorkflowNode
from src.llm_client import LLMClient
from src.plugins.contracts import PluginInput, PluginOutput, PluginSpec
from src.plugins.registry import PluginRegistry
from src.schemas import FinalAnswer

# ---------------------------------------------------------------------------
# Fake plugin for tests
# ---------------------------------------------------------------------------


@dataclass
class FakePlugin:
    name: str = "test_plugin"
    kind: str = "test"
    version: str = "1.0.0"
    description: str = "A fake plugin for testing"
    result: str = "fake_result"

    spec: PluginSpec = field(init=False)

    def __post_init__(self) -> None:
        self.spec = PluginSpec(
            name=self.name,
            kind=self.kind,
            version=self.version,
            description=self.description,
        )

    def execute(self, input: PluginInput) -> PluginOutput:
        return PluginOutput(
            data={
                "result": self.result,
                "input_length": len(input.data.get("text", "")),
            }
        )


def _make_node(node_id: str, intent: str = "general") -> WorkflowNode:
    class _Node:
        id = intent

        def execute(self, input: str, llm: LLMClient) -> FinalAnswer:
            return FinalAnswer(answer=f"{self.id}:{input}")

    return _Node()


def _expect_final_answer(result: object) -> FinalAnswer:
    assert isinstance(result, FinalAnswer)
    return result


# ===================================================================
# PluginSpec
# ===================================================================


class TestPluginSpec:
    def test_holds_all_fields(self) -> None:
        spec = PluginSpec(
            name="ner.default",
            kind="technique",
            version="1.0.0",
            description="NER plugin",
        )
        assert spec.name == "ner.default"
        assert spec.kind == "technique"
        assert spec.version == "1.0.0"
        assert spec.description == "NER plugin"

    def test_description_defaults_to_empty(self) -> None:
        spec = PluginSpec(name="x", kind="y", version="1")
        assert spec.description == ""


# ===================================================================
# PluginRegistry
# ===================================================================


class TestPluginRegistry:
    def test_register_and_resolve(self) -> None:
        registry = PluginRegistry()
        plugin = FakePlugin(name="my_plugin")
        registry.register(plugin)

        resolved = registry.resolve("my_plugin")
        assert resolved is plugin

    def test_resolve_returns_correct_plugin_by_name(self) -> None:
        registry = PluginRegistry()
        a = FakePlugin(name="alpha")
        b = FakePlugin(name="beta")
        registry.register(a)
        registry.register(b)

        assert registry.resolve("alpha") is a
        assert registry.resolve("beta") is b

    def test_duplicate_registration_raises(self) -> None:
        registry = PluginRegistry()
        registry.register(FakePlugin(name="dup"))

        with pytest.raises(ValueError, match="Duplicate plugin registration.*dup"):
            registry.register(FakePlugin(name="dup"))

    def test_unknown_plugin_resolve_raises(self) -> None:
        registry = PluginRegistry()

        with pytest.raises(KeyError, match="Unknown plugin.*nonexistent"):
            registry.resolve("nonexistent")

    def test_unknown_plugin_error_includes_registered_names(self) -> None:
        registry = PluginRegistry()
        registry.register(FakePlugin(name="ner.default"))
        registry.register(FakePlugin(name="scoring.default"))

        with pytest.raises(KeyError, match="ner.default.*scoring.default"):
            registry.resolve("nope")

    def test_registered_names_returns_sorted_list(self) -> None:
        registry = PluginRegistry()
        registry.register(FakePlugin(name="z_plugin"))
        registry.register(FakePlugin(name="a_plugin"))
        registry.register(FakePlugin(name="m_plugin"))

        assert registry.registered_names == ["a_plugin", "m_plugin", "z_plugin"]

    def test_registered_count(self) -> None:
        registry = PluginRegistry()
        assert registry.registered_count == 0
        registry.register(FakePlugin(name="a"))
        assert registry.registered_count == 1

    def test_items_returns_copy_of_registry(self) -> None:
        registry = PluginRegistry()
        p = FakePlugin(name="p")
        registry.register(p)

        items = registry.items()
        assert items == {"p": p}
        # Mutating the returned dict does not affect the registry
        items.clear()
        assert registry.resolve("p") is p


# ===================================================================
# PluginNode
# ===================================================================


class TestPluginNode:
    def test_executes_plugin_through_registry(self) -> None:
        registry = PluginRegistry()
        plugin = FakePlugin(name="greeter", result="hello from plugin")
        registry.register(plugin)

        from src.nodes.plugin_node import PluginNode

        node = PluginNode("greeter", registry)
        result = node.execute("world", MagicMock())

        assert isinstance(result, FinalAnswer)
        assert result.answer == "hello from plugin"

    def test_unknown_plugin_raises_at_execution_time(self) -> None:
        registry = PluginRegistry()

        from src.nodes.plugin_node import PluginNode

        node = PluginNode("missing", registry)

        with pytest.raises(KeyError, match="Unknown plugin.*missing"):
            node.execute("any", MagicMock())

    def test_replacing_plugin_implementation_does_not_require_node_change(
        self,
    ) -> None:
        """PluginNode holds a reference to the registry, not the Plugin instance."""
        registry = PluginRegistry()

        class FirstImpl:
            spec = PluginSpec(name="dynamic", kind="test", version="1")

            def execute(self, input: PluginInput) -> PluginOutput:
                return PluginOutput(data={"result": "first_impl"})

        class SecondImpl:
            spec = PluginSpec(name="dynamic", kind="test", version="2")

            def execute(self, input: PluginInput) -> PluginOutput:
                return PluginOutput(data={"result": "second_impl"})

        registry.register(FirstImpl())

        from src.nodes.plugin_node import PluginNode

        node = PluginNode("dynamic", registry)

        # Replace implementation at the registry level
        registry._plugins["dynamic"] = SecondImpl()

        result = _expect_final_answer(node.execute("input", MagicMock()))
        assert result.answer == "second_impl"

    def test_plugin_node_id_format(self) -> None:
        from src.nodes.plugin_node import PluginNode

        registry = PluginRegistry()
        registry.register(FakePlugin(name="my_tech"))
        node = PluginNode("my_tech", registry)

        assert node.id == "plugin_my_tech"

    def test_namespaced_plugin_ids_work(self) -> None:
        registry = PluginRegistry()
        registry.register(FakePlugin(name="ner.default", result="ENTITIES"))
        registry.register(FakePlugin(name="scoring.default", result="SCORE"))

        from src.nodes.plugin_node import PluginNode

        ner_node = PluginNode("ner.default", registry)
        score_node = PluginNode("scoring.default", registry)

        assert ner_node.id == "plugin_ner.default"
        assert score_node.id == "plugin_scoring.default"
        assert _expect_final_answer(ner_node.execute("input", MagicMock())).answer == "ENTITIES"
        assert _expect_final_answer(score_node.execute("input", MagicMock())).answer == "SCORE"


# ===================================================================
# PluginNode inside DAG executor
# ===================================================================


class TestPluginNodeInDAG:
    def test_dag_executes_plugin_node_through_registry(self) -> None:
        registry = PluginRegistry()
        plugin = FakePlugin(name="greeter", result="plugin says hi")
        registry.register(plugin)

        from src.nodes.plugin_node import PluginNode

        node = PluginNode("greeter", registry)

        graph = DagWorkflow(
            name="plugin_dag",
            description="dag with plugin node",
            nodes=(
                DagNode("first", _make_node("a", "first"), "prepare {query}"),
                DagNode(
                    "second",
                    node,
                    "{first}",
                    depends_on=("first",),
                ),
            ),
            final_node="second",
        )

        result, trace = run_dag_workflow(graph, "hello", MagicMock())
        final = _expect_final_answer(result)
        assert final.answer == "plugin says hi"
        assert trace.nodes["second"].output == "plugin says hi"

    def test_dag_executes_plugin_node_without_knowing_plugin_type(self) -> None:
        """The DAG executor sees only WorkflowNode, never Plugin or PluginRegistry."""
        registry = PluginRegistry()
        registry.register(FakePlugin(name="hidden"))

        from src.nodes.plugin_node import PluginNode

        node = PluginNode("hidden", registry)

        graph = DagWorkflow(
            name="blind_dag",
            description="dag executor is blind to plugin type",
            nodes=(DagNode("only", node, "{query}"),),
            final_node="only",
        )

        result, trace = run_dag_workflow(graph, "test", MagicMock())
        assert _expect_final_answer(result).answer == "fake_result"

    def test_replacing_plugin_produces_different_output_without_dag_change(
        self,
    ) -> None:
        registry = PluginRegistry()

        class OldImpl:
            spec = PluginSpec(name="swappable", kind="test", version="1")

            def execute(self, input: PluginInput) -> PluginOutput:
                return PluginOutput(data={"result": "old_output"})

        registry.register(OldImpl())

        from src.nodes.plugin_node import PluginNode

        node = PluginNode("swappable", registry)
        dag = DagWorkflow(
            name="swap_dag",
            description="test",
            nodes=(DagNode("n", node, "{query}"),),
            final_node="n",
        )

        result1, _ = run_dag_workflow(dag, "x", MagicMock())
        assert _expect_final_answer(result1).answer == "old_output"

        class NewImpl:
            spec = PluginSpec(name="swappable", kind="test", version="2")

            def execute(self, input: PluginInput) -> PluginOutput:
                return PluginOutput(data={"result": "new_output"})

        registry._plugins["swappable"] = NewImpl()

        result2, _ = run_dag_workflow(dag, "x", MagicMock())
        assert _expect_final_answer(result2).answer == "new_output"


# ===================================================================
# DAG executor import isolation
# ===================================================================


class TestDAGExecutorDoesNotImportConcreteModules:
    """dag.py must stay free of concrete plugin, technique, and tool imports."""

    def test_dag_module_source_contains_no_plugin_imports(self) -> None:
        import inspect

        import src.dag

        source = inspect.getsource(src.dag)
        forbidden = [
            "src.plugin",
            "src.plugins",
            "src.ner",
            "src.scoring",
            "src.techniques",
            "src.tools.calculator",
            "from src.nodes.plugin_node",
        ]
        for token in forbidden:
            assert token not in source, f"dag.py must not import {token!r} — found in source"

    def test_importing_dag_does_not_transitively_import_plugins(
        self,
    ) -> None:
        before = {
            k for k in sys.modules if k.startswith(("src.plugin", "src.plugins", "src.techniques"))
        }

        import importlib

        import src.dag

        importlib.reload(src.dag)

        after = {
            k for k in sys.modules if k.startswith(("src.plugin", "src.plugins", "src.techniques"))
        }

        newly_loaded = after - before
        assert not newly_loaded, f"Importing dag.py loaded plugin modules: {newly_loaded}"


class TestTechniqueDoesNotImportDAG:
    """technique modules must not import dag, perform composition, or register conditions."""

    def test_techniques_retrieval_does_not_import_dag(self) -> None:
        import inspect

        import src.techniques.retrieval

        source = inspect.getsource(src.techniques.retrieval)
        assert "src.dag" not in source, "src.techniques.retrieval must not import src.dag"

    def test_techniques_fuzzy_has_no_dag_import(self) -> None:
        import inspect

        import src.techniques.fuzzy

        source = inspect.getsource(src.techniques.fuzzy)
        assert "src.dag" not in source, "src.techniques.fuzzy must not import src.dag"

    def test_techniques_fuzzy_has_no_side_effects_on_import(self) -> None:
        from src.dag import CONDITION_REGISTRY

        before = set(CONDITION_REGISTRY.keys())

        import importlib

        import src.techniques.fuzzy

        importlib.reload(src.techniques.fuzzy)

        after = set(CONDITION_REGISTRY.keys())
        assert after == before, (
            f"Importing src.techniques.fuzzy registered conditions: {after - before}"
        )

    def test_importing_techniques_retrieval_does_not_register_dag_conditions(
        self,
    ) -> None:
        import importlib

        from src.dag import CONDITION_REGISTRY

        before = set(CONDITION_REGISTRY.keys())

        import src.techniques.retrieval

        importlib.reload(src.techniques.retrieval)

        after = set(CONDITION_REGISTRY.keys())
        newly_registered = after - before

        assert "if_retrieval_needed" not in newly_registered, (
            "Importing src.techniques.retrieval must not register DAG conditions"
        )
        assert "if_not_retrieval_needed" not in newly_registered


# ===================================================================
# No global registry side effects from importing src.plugins
# ===================================================================


class TestNoGlobalPluginRegistrySideEffects:
    def test_importing_src_plugins_has_no_side_effects(self) -> None:
        """src.plugins.__init__ must not create a global PLUGIN_REGISTRY."""
        import importlib

        import src.plugins

        importlib.reload(src.plugins)

        # No PLUGIN_REGISTRY attribute should exist
        assert not hasattr(src.plugins, "PLUGIN_REGISTRY")

        # No module-level registration should have occurred
        # Check that the contracts are importable but no registry exists
        from src.plugins.contracts import PluginSpec

        assert PluginSpec is not None


# ===================================================================
# build_plugin_registry() produces correctly named plugins
# ===================================================================


class TestBuildPluginRegistry:
    def test_build_plugin_registry_returns_populated_registry(self) -> None:
        from src.plugins.manifest import build_plugin_registry

        registry = build_plugin_registry()
        assert registry.registered_count == 4
        assert "ner.default" in registry.registered_names
        assert "scoring.default" in registry.registered_names
        assert "retrieval.default" in registry.registered_names
        assert "tool.calculator" in registry.registered_names

    def test_plugin_names_are_namespaced(self) -> None:
        from src.plugins.manifest import build_plugin_registry

        registry = build_plugin_registry()

        ner = registry.resolve("ner.default")
        assert ner.spec.name == "ner.default"
        assert ner.spec.kind == "technique"

        scoring = registry.resolve("scoring.default")
        assert scoring.spec.name == "scoring.default"
        assert scoring.spec.kind == "technique"

        retrieval = registry.resolve("retrieval.default")
        assert retrieval.spec.name == "retrieval.default"
        assert retrieval.spec.kind == "technique"

        calc = registry.resolve("tool.calculator")
        assert calc.spec.name == "tool.calculator"
        assert calc.spec.kind == "tool"


# ===================================================================
# Concrete technique plugins
# ===================================================================


class TestConcreteNERPlugin:
    def test_ner_plugin_can_be_registered_and_resolved(self) -> None:
        from src.plugins.manifest import build_plugin_registry

        registry = build_plugin_registry()
        plugin = registry.resolve("ner.default")
        assert plugin.spec.name == "ner.default"
        assert "entity" in plugin.spec.description.lower()

    def test_ner_plugin_execution_without_spacy(self) -> None:
        """NERPlugin.execute works even when spaCy model is absent
        (it returns 'no entities found')."""
        from src.plugins.techniques.ner import NERPlugin

        plugin = NERPlugin()
        output = plugin.execute(PluginInput(data={"text": "hello world"}))
        assert isinstance(output.data["result"], str)


class TestConcreteScoringPlugin:
    def test_scoring_plugin_can_be_registered(self) -> None:
        from src.plugins.manifest import build_plugin_registry

        registry = build_plugin_registry()
        plugin = registry.resolve("scoring.default")
        assert plugin.spec.name == "scoring.default"

    def test_scoring_plugin_scores_text(self) -> None:
        from src.plugins.techniques.scoring import ScoringPlugin

        plugin = ScoringPlugin()
        output = plugin.execute(PluginInput(data={"text": "good quality text here"}))
        assert "quality=" in output.data["result"]
        assert "usable=" in output.data["result"]
        assert output.data["quality"] > 0

    def test_scoring_plugin_empty_text(self) -> None:
        from src.plugins.techniques.scoring import ScoringPlugin

        plugin = ScoringPlugin()
        output = plugin.execute(PluginInput(data={"text": ""}))
        assert output.data["is_usable"] is False
        assert "empty" in output.data["reason"]


# ===================================================================
# Concrete tool plugins
# ===================================================================


class TestConcreteRetrievalPlugin:
    def test_retrieval_plugin_can_be_registered(self) -> None:
        from src.plugins.manifest import build_plugin_registry

        registry = build_plugin_registry()
        plugin = registry.resolve("retrieval.default")
        assert plugin.spec.name == "retrieval.default"
        assert "retrieve" in plugin.spec.description.lower()

    def test_retrieval_plugin_executes_through_plugin_node(self) -> None:
        from src.plugins.techniques.retrieval import RetrievalPlugin

        plugin = RetrievalPlugin()
        output = plugin.execute(PluginInput(data={"text": "hello world"}))
        assert "result" in output.data
        assert "length" in output.data

    def test_retrieval_plugin_node_in_dag_works_with_mock_registry(
        self,
    ) -> None:
        from src.plugins.techniques.retrieval import RetrievalPlugin

        registry = PluginRegistry()
        registry.register(RetrievalPlugin())

        from src.nodes.plugin_node import PluginNode

        node = PluginNode("retrieval.default", registry)
        result = node.execute("test", MagicMock())
        assert isinstance(result, FinalAnswer)


class TestConcreteCalculatorPlugin:
    def test_calculator_plugin_can_be_registered(self) -> None:
        from src.plugins.manifest import build_plugin_registry

        registry = build_plugin_registry()
        plugin = registry.resolve("tool.calculator")
        assert plugin.spec.name == "tool.calculator"

    def test_calculator_plugin_evaluates_expression(self) -> None:
        from src.plugins.tools.calculator import CalculatorPlugin

        plugin = CalculatorPlugin()
        output = plugin.execute(PluginInput(data={"text": "2 + 3"}))
        assert output.data["result"] == "5"

    def test_calculator_plugin_complex_expression(self) -> None:
        from src.plugins.tools.calculator import CalculatorPlugin

        plugin = CalculatorPlugin()
        output = plugin.execute(PluginInput(data={"text": "sqrt(16) * 2"}))
        assert output.data["result"] == "8"


# ===================================================================
# NODE_REGISTRY integration — plugin nodes are reachable
# ===================================================================


class TestPluginNodesInDefaultRegistry:
    """Plugin nodes live in the NodeRegistry built by build_node_registry."""

    def test_plugin_scoring_node_is_registered(self) -> None:
        from src.bootstrap import build_node_registry, build_tool_registry

        registry = build_node_registry(tool_registry=build_tool_registry())
        node = registry.get("plugin_scoring.default")
        assert node is not None
        assert node.id == "plugin_scoring.default"

    def test_plugin_ner_node_is_registered(self) -> None:
        from src.bootstrap import build_node_registry, build_tool_registry

        registry = build_node_registry(tool_registry=build_tool_registry())
        node = registry.get("plugin_ner.default")
        assert node is not None
        assert node.id == "plugin_ner.default"

    def test_plugin_retrieval_node_is_registered(self) -> None:
        from src.bootstrap import build_node_registry, build_tool_registry

        registry = build_node_registry(tool_registry=build_tool_registry())
        node = registry.get("plugin_retrieval.default")
        assert node is not None
        assert node.id == "plugin_retrieval.default"

    def test_plugin_calculator_node_is_registered(self) -> None:
        from src.bootstrap import build_node_registry, build_tool_registry

        registry = build_node_registry(tool_registry=build_tool_registry())
        node = registry.get("plugin_tool.calculator")
        assert node is not None
        assert node.id == "plugin_tool.calculator"

    def test_handlers_has_no_node_registry(self) -> None:
        """Importing handlers does not create a NODE_REGISTRY."""
        import src.handlers

        assert not hasattr(src.handlers, "NODE_REGISTRY")


# ===================================================================
# handlers import must not build a plugin registry
# ===================================================================


class TestHandlersNoPluginSideEffects:
    """Importing src.handlers must not trigger plugin construction."""

    def test_importing_handlers_module_source_has_no_plugin_references(
        self,
    ) -> None:
        import inspect

        import src.handlers

        source = inspect.getsource(src.handlers)
        forbidden = [
            "build_plugin_registry",
            "src.plugins",
            "PluginNode",
            "plugin_registry",
        ]
        for token in forbidden:
            assert token not in source, f"handlers/__init__.py must not reference {token!r}"

    def test_importing_handlers_does_not_load_plugin_modules(
        self,
    ) -> None:
        before = {k for k in sys.modules if k.startswith(("src.plugin", "src.plugins"))}

        import importlib

        import src.handlers

        importlib.reload(src.handlers)

        after = {k for k in sys.modules if k.startswith(("src.plugin", "src.plugins"))}

        newly_loaded = after - before
        assert not newly_loaded, f"Importing handlers loaded plugin modules: {newly_loaded}"


# ===================================================================
# Workflow integration — plugin_demo workflow
# ===================================================================


class TestPluginDemoWorkflow:
    def test_plugin_demo_workflow_exists_and_uses_plugin_nodes(self) -> None:
        from src.bootstrap import build_node_registry, build_tool_registry
        from src.workflow import get_workflow_registry, set_node_registry

        set_node_registry(build_node_registry(tool_registry=build_tool_registry()))
        wf = get_workflow_registry()["plugin_demo"]
        node_ids = {n.id for n in wf.nodes}
        assert "extract" in node_ids
        assert "score" in node_ids

        extract_node = next(n for n in wf.nodes if n.id == "extract")
        score_node = next(n for n in wf.nodes if n.id == "score")
        assert extract_node.node.id == "plugin_ner.default"
        assert score_node.node.id == "plugin_scoring.default"

    def test_plugin_demo_workflow_dag_validation(self) -> None:
        from src.bootstrap import build_node_registry, build_tool_registry
        from src.workflow import get_workflow_registry, set_node_registry

        set_node_registry(build_node_registry(tool_registry=build_tool_registry()))
        wf = get_workflow_registry()["plugin_demo"]
        assert wf.final_node == "score"

    def test_plugin_node_executes_with_mock_in_dag(self) -> None:
        registry = PluginRegistry()
        registry.register(FakePlugin(name="ner.default", result="NER: OpenAI"))
        registry.register(FakePlugin(name="scoring.default", result="SCORE: ok"))

        from src.nodes.plugin_node import PluginNode

        wf = DagWorkflow(
            name="plugin_demo_mock",
            description="test",
            nodes=(
                DagNode(
                    "extract",
                    PluginNode("ner.default", registry),
                    "{query}",
                ),
                DagNode(
                    "score",
                    PluginNode("scoring.default", registry),
                    "{extract}",
                    depends_on=("extract",),
                ),
            ),
            final_node="score",
        )

        result, trace = run_dag_workflow(wf, "hello", MagicMock())
        assert _expect_final_answer(result).answer == "SCORE: ok"
        assert trace.nodes["extract"].output == "NER: OpenAI"


# ===================================================================
# Backward compatibility — src.plugin re-exports
# ===================================================================


class TestCanonicalPaths:
    def test_src_plugin_contracts_importable(self) -> None:
        from src.plugins.contracts import PluginInput, PluginOutput, PluginSpec

        assert PluginInput is not None
        assert PluginOutput is not None

        spec = PluginSpec(name="x", kind="y", version="1")
        assert spec.name == "x"

    def test_src_plugin_registry_importable(self) -> None:
        from src.plugins.registry import PluginRegistry

        assert PluginRegistry is not None
        r = PluginRegistry()
        assert r.registered_count == 0

    def test_src_techniques_ner_importable(self) -> None:
        from src.techniques.ner import Entity, extract, is_temporal

        assert Entity is not None
        assert extract is not None
        assert is_temporal is not None

    def test_src_techniques_scoring_importable(self) -> None:
        from src.techniques.scoring import ResultScore, score_result

        assert ResultScore is not None
        result = score_result("hello world")
        assert result.is_usable

    def test_ner_plugin_canonical_path(self) -> None:
        from src.plugins.techniques.ner import NERPlugin

        assert NERPlugin is not None
        assert NERPlugin.spec.name == "ner.default"

    def test_scoring_plugin_canonical_path(self) -> None:
        from src.plugins.techniques.scoring import ScoringPlugin

        assert ScoringPlugin is not None
        assert ScoringPlugin.spec.name == "scoring.default"

    def test_calculator_plugin_canonical_path(self) -> None:
        from src.plugins.tools.calculator import CalculatorPlugin

        assert CalculatorPlugin is not None
        assert CalculatorPlugin.spec.name == "tool.calculator"

    def test_src_techniques_retrieval_importable(self) -> None:
        from src.techniques.retrieval import Retriever, needs_retrieval

        assert Retriever is not None
        assert needs_retrieval("latest news") is True

    def test_retrievers_default_importable(self) -> None:
        from src.retrievers.default import DefaultRetriever, create_default_retriever

        assert DefaultRetriever is not None
        assert create_default_retriever is not None

    def test_retrieval_plugin_path_works(self) -> None:
        from src.plugins.techniques.retrieval import RetrievalPlugin

        assert RetrievalPlugin is not None

    def test_replacing_retrieval_plugin_chains_through_registry(self) -> None:
        """Replacing retrieval.default changes PluginNode output without
        changing the node instance or DAG."""
        registry = PluginRegistry()

        class FakeRetrieval:
            spec = PluginSpec(
                name="retrieval.default",
                kind="technique",
                version="1.0.0",
                description="fake",
            )

            def execute(self, input: PluginInput) -> PluginOutput:
                return PluginOutput(data={"result": "fake_context"})

        registry.register(FakeRetrieval())

        from src.nodes.plugin_node import PluginNode

        node = PluginNode("retrieval.default", registry)

        result1 = _expect_final_answer(node.execute("test", MagicMock()))
        assert result1.answer == "fake_context"

        class NewFakeRetrieval:
            spec = PluginSpec(
                name="retrieval.default",
                kind="technique",
                version="2.0.0",
                description="fake v2",
            )

            def execute(self, input: PluginInput) -> PluginOutput:
                return PluginOutput(data={"result": "new_fake_context"})

        registry._plugins["retrieval.default"] = NewFakeRetrieval()

        result2 = _expect_final_answer(node.execute("test", MagicMock()))
        assert result2.answer == "new_fake_context"

    def test_src_techniques_fuzzy_importable(self) -> None:
        from src.techniques.fuzzy import match_workflow, normalize_query

        assert match_workflow is not None
        assert normalize_query is not None
        assert normalize_query("the quick brown fox") == "quick brown fox"
