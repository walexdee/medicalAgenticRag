"""
Unit tests for backend/pipeline/nodes.py

All OpenAI and ChromaDB calls are mocked — no network I/O.
"""
import pytest
from unittest.mock import MagicMock, patch

from tests.conftest import make_state


# ---------------------------------------------------------------------------
# router_node
# ---------------------------------------------------------------------------

class TestRouterNode:
    def test_routes_to_qna(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(return_value="Retrieve_QnA"))
        state = make_state(query="What causes diabetes?")
        result = nodes.router_node(state)
        assert result["source"] == "Retrieve_QnA"
        assert result["source_routing"] == "Retrieve_QnA"

    def test_routes_to_device(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(return_value="Retrieve_Device"))
        state = make_state(query="How do I use a ventilator?")
        result = nodes.router_node(state)
        assert result["source"] == "Retrieve_Device"

    def test_routes_to_web_search(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(return_value="Web_Search"))
        state = make_state(query="Latest COVID-19 news")
        result = nodes.router_node(state)
        assert result["source"] == "Web_Search"

    def test_invalid_llm_response_falls_back_to_web_search(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(return_value="InvalidOption"))
        state = make_state(query="Random query")
        result = nodes.router_node(state)
        assert result["source"] == "Web_Search"

    def test_source_reason_set(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(return_value="Retrieve_QnA"))
        state = make_state()
        result = nodes.router_node(state)
        assert "source_reason" in result
        assert len(result["source_reason"]) > 0


# ---------------------------------------------------------------------------
# route_decision
# ---------------------------------------------------------------------------

class TestRouteDecision:
    def test_returns_source(self):
        from backend.pipeline.nodes import route_decision
        state = make_state(source="Retrieve_QnA")
        assert route_decision(state) == "Retrieve_QnA"


# ---------------------------------------------------------------------------
# retrieve_qna
# ---------------------------------------------------------------------------

class TestRetrieveQnA:
    def test_populates_context(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "query_qna", MagicMock(return_value=["Doc 1: Diabetes info.", "Doc 2: More."]))
        state = make_state(query="What is diabetes?")
        result = nodes.retrieve_qna(state)
        assert result["context"] != ""
        assert result["source"] == "Medical Q&A Collection"

    def test_handles_empty_results(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "query_qna", MagicMock(return_value=[]))
        state = make_state(query="obscure query")
        result = nodes.retrieve_qna(state)
        assert result["context"] == ""

    def test_handles_exception_gracefully(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "query_qna", MagicMock(side_effect=RuntimeError("DB error")))
        state = make_state()
        result = nodes.retrieve_qna(state)
        assert result["context"] == ""


# ---------------------------------------------------------------------------
# retrieve_device
# ---------------------------------------------------------------------------

class TestRetrieveDevice:
    def test_populates_context(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "query_device", MagicMock(return_value=["Pacemaker doc 1.", "Pacemaker doc 2."]))
        state = make_state(query="How does a pacemaker work?")
        result = nodes.retrieve_device(state)
        assert result["context"] != ""
        assert result["source"] == "Medical Device Manual"

    def test_handles_exception_gracefully(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "query_device", MagicMock(side_effect=RuntimeError("DB error")))
        state = make_state()
        result = nodes.retrieve_device(state)
        assert result["context"] == ""


# ---------------------------------------------------------------------------
# web_search_node
# ---------------------------------------------------------------------------

class TestWebSearchNode:
    def test_populates_context_on_success(self, monkeypatch):
        mock_results = [{"body": "COVID news article 1."}, {"body": "COVID news article 2."}]
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = mock_results
        monkeypatch.setattr("backend.pipeline.nodes.DDGS", MagicMock(return_value=mock_ddgs))

        from backend.pipeline import nodes
        state = make_state(query="Latest COVID news")
        result = nodes.web_search_node(state)
        assert "COVID news article 1." in result["context"]
        assert result["source"] == "Web Search (DuckDuckGo)"

    def test_empty_results(self, monkeypatch):
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = []
        monkeypatch.setattr("backend.pipeline.nodes.DDGS", MagicMock(return_value=mock_ddgs))

        from backend.pipeline import nodes
        state = make_state(query="very obscure query")
        result = nodes.web_search_node(state)
        assert result["context"] == "No results found"

    def test_handles_exception_gracefully(self, monkeypatch):
        monkeypatch.setattr(
            "backend.pipeline.nodes.DDGS",
            MagicMock(side_effect=RuntimeError("Network error")),
        )
        from backend.pipeline import nodes
        state = make_state()
        result = nodes.web_search_node(state)
        assert "Search error" in result["context"]
        assert result["source"] == "Web Search (failed)"


# ---------------------------------------------------------------------------
# relevance_checker
# ---------------------------------------------------------------------------

class TestRelevanceChecker:
    def test_marks_relevant_yes(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(return_value="Yes"))
        state = make_state(iteration_count=0)
        result = nodes.relevance_checker(state)
        assert result["is_relevant"] == "Yes"
        assert result["iteration_count"] == 1

    def test_marks_relevant_no(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(return_value="No"))
        state = make_state(iteration_count=0)
        result = nodes.relevance_checker(state)
        assert result["is_relevant"] == "No"

    def test_max_iterations_forces_relevant(self, monkeypatch):
        from backend.pipeline import nodes
        from backend.config import MAX_ITERATIONS
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(return_value="No"))
        # iteration_count starts at MAX_ITERATIONS - 1, checker increments it to MAX
        state = make_state(iteration_count=MAX_ITERATIONS - 1)
        result = nodes.relevance_checker(state)
        assert result["is_relevant"] == "Yes"
        assert result["iteration_count"] == MAX_ITERATIONS

    def test_increments_iteration_count(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(return_value="Yes"))
        state = make_state(iteration_count=1)
        result = nodes.relevance_checker(state)
        assert result["iteration_count"] == 2

    def test_handles_llm_exception(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(side_effect=RuntimeError("LLM down")))
        state = make_state(iteration_count=0)
        result = nodes.relevance_checker(state)
        # On error defaults to relevant so we don't loop forever
        assert result["is_relevant"] == "Yes"


# ---------------------------------------------------------------------------
# relevance_decision
# ---------------------------------------------------------------------------

class TestRelevanceDecision:
    def test_returns_is_relevant_field(self):
        from backend.pipeline.nodes import relevance_decision
        state = make_state(is_relevant="Yes")
        assert relevance_decision(state) == "Yes"

    def test_returns_no(self):
        from backend.pipeline.nodes import relevance_decision
        state = make_state(is_relevant="No")
        assert relevance_decision(state) == "No"


# ---------------------------------------------------------------------------
# augment_node
# ---------------------------------------------------------------------------

class TestAugmentNode:
    def test_builds_prompt_with_context(self):
        from backend.pipeline.nodes import augment_node
        state = make_state(context="Diabetes is a metabolic disease.", history=[])
        result = augment_node(state)
        assert "Diabetes is a metabolic disease." in result["prompt"]
        assert "What are symptoms of diabetes?" in result["prompt"]

    def test_includes_history_block(self):
        from backend.pipeline.nodes import augment_node
        history = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there"}]
        state = make_state(history=history)
        result = augment_node(state)
        assert "Previous conversation:" in result["prompt"]
        assert "Hello" in result["prompt"]

    def test_empty_context_message(self):
        from backend.pipeline.nodes import augment_node
        state = make_state(context="")
        result = augment_node(state)
        assert "No relevant context was retrieved." in result["prompt"]

    def test_no_history_no_history_block(self):
        from backend.pipeline.nodes import augment_node
        state = make_state(history=[])
        result = augment_node(state)
        assert "Previous conversation:" not in result["prompt"]


# ---------------------------------------------------------------------------
# generate_node
# ---------------------------------------------------------------------------

class TestGenerateNode:
    def test_generates_response(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(return_value="Generated answer."))
        state = make_state(prompt="Answer the question about diabetes.")
        result = nodes.generate_node(state)
        assert result["response"] == "Generated answer."
        assert 0.0 <= result["confidence"] <= 1.0

    def test_handles_llm_error(self, monkeypatch):
        from backend.pipeline import nodes
        monkeypatch.setattr(nodes, "get_llm_response", MagicMock(side_effect=RuntimeError("API error")))
        state = make_state(prompt="Some prompt")
        result = nodes.generate_node(state)
        assert "Error generating response" in result["response"]
        assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# _build_history_block (internal helper)
# ---------------------------------------------------------------------------

class TestBuildHistoryBlock:
    def test_empty_history(self):
        from backend.pipeline.nodes import _build_history_block
        assert _build_history_block([]) == ""

    def test_formats_user_and_assistant(self):
        from backend.pipeline.nodes import _build_history_block
        history = [
            {"role": "user", "content": "What is aspirin?"},
            {"role": "assistant", "content": "Aspirin is an analgesic."},
        ]
        block = _build_history_block(history)
        assert "User: What is aspirin?" in block
        assert "Assistant: Aspirin is an analgesic." in block
        assert block.startswith("Previous conversation:")
