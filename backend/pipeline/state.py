from backend.models import GraphState


def compute_confidence(state: GraphState) -> float:
    """Heuristic confidence based on source quality, relevance, and iteration count."""
    source = state.get("source", "")
    is_relevant = state.get("is_relevant", "No").lower() == "yes"
    iterations = state.get("iteration_count", 1)

    if "Q&A" in source:
        base = 0.90
    elif "Device" in source:
        base = 0.85
    elif "Web Search" in source and "failed" not in source:
        base = 0.65
    else:
        base = 0.40

    if not is_relevant:
        base -= 0.15

    base -= max(0, iterations - 1) * 0.08

    return round(max(0.0, min(1.0, base)), 2)
