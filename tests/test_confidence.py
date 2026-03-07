"""
Unit tests for backend/pipeline/state.py :: compute_confidence
"""
import pytest
from tests.conftest import make_state
from backend.pipeline.state import compute_confidence


class TestComputeConfidence:
    # ── Source-based base scores ──────────────────────────────────────────

    def test_qna_source_base(self):
        state = make_state(source="Medical Q&A Collection", is_relevant="Yes", iteration_count=1)
        assert compute_confidence(state) == pytest.approx(0.90)

    def test_device_source_base(self):
        state = make_state(source="Medical Device Manual", is_relevant="Yes", iteration_count=1)
        assert compute_confidence(state) == pytest.approx(0.85)

    def test_web_search_source_base(self):
        state = make_state(source="Web Search (DuckDuckGo)", is_relevant="Yes", iteration_count=1)
        assert compute_confidence(state) == pytest.approx(0.65)

    def test_failed_web_search_source(self):
        state = make_state(source="Web Search (failed)", is_relevant="Yes", iteration_count=1)
        assert compute_confidence(state) == pytest.approx(0.40)

    def test_unknown_source_falls_to_default(self):
        state = make_state(source="Unknown Source", is_relevant="Yes", iteration_count=1)
        assert compute_confidence(state) == pytest.approx(0.40)

    # ── Relevance penalty ─────────────────────────────────────────────────

    def test_not_relevant_penalises_score(self):
        state = make_state(source="Medical Q&A Collection", is_relevant="No", iteration_count=1)
        # 0.90 - 0.15 = 0.75
        assert compute_confidence(state) == pytest.approx(0.75)

    def test_not_relevant_web_search(self):
        state = make_state(source="Web Search (DuckDuckGo)", is_relevant="No", iteration_count=1)
        # 0.65 - 0.15 = 0.50
        assert compute_confidence(state) == pytest.approx(0.50)

    # ── Iteration penalty ─────────────────────────────────────────────────

    def test_second_iteration_penalises(self):
        state = make_state(source="Medical Q&A Collection", is_relevant="Yes", iteration_count=2)
        # 0.90 - 0.08 = 0.82
        assert compute_confidence(state) == pytest.approx(0.82)

    def test_third_iteration_penalises(self):
        state = make_state(source="Medical Q&A Collection", is_relevant="Yes", iteration_count=3)
        # 0.90 - 0.16 = 0.74
        assert compute_confidence(state) == pytest.approx(0.74)

    def test_first_iteration_no_penalty(self):
        state = make_state(source="Medical Device Manual", is_relevant="Yes", iteration_count=1)
        # max(0, 1-1) * 0.08 = 0
        assert compute_confidence(state) == pytest.approx(0.85)

    # ── Floor / ceiling clamping ──────────────────────────────────────────

    def test_score_never_below_zero(self):
        # worst case: unknown source (0.40), not relevant (-0.15), many iterations
        state = make_state(source="Unknown", is_relevant="No", iteration_count=10)
        assert compute_confidence(state) >= 0.0

    def test_score_never_above_one(self):
        state = make_state(source="Medical Q&A Collection", is_relevant="Yes", iteration_count=1)
        assert compute_confidence(state) <= 1.0

    # ── Combining penalties ───────────────────────────────────────────────

    def test_combined_penalties(self):
        state = make_state(source="Medical Q&A Collection", is_relevant="No", iteration_count=3)
        # 0.90 - 0.15 - 0.16 = 0.59
        assert compute_confidence(state) == pytest.approx(0.59)

    def test_is_relevant_case_insensitive(self):
        state_upper = make_state(source="Medical Q&A Collection", is_relevant="YES", iteration_count=1)
        state_lower = make_state(source="Medical Q&A Collection", is_relevant="yes", iteration_count=1)
        assert compute_confidence(state_upper) == compute_confidence(state_lower)
