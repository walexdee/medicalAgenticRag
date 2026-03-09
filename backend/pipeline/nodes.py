import logging
from typing import List

from openai import OpenAI
from duckduckgo_search import DDGS

from backend.config import OPENAI_API_KEY, LLM_MODEL, MAX_ITERATIONS
from backend.models import GraphState
from backend.vector_store import query_qna, query_device
from backend.pipeline.state import compute_confidence

logger = logging.getLogger(__name__)

_openai_client = OpenAI(api_key=OPENAI_API_KEY)


def get_llm_response(prompt: str, temperature: float = 0.5) -> str:
    try:
        response = _openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise


def router_node(state: GraphState) -> GraphState:
    prompt = f"""You are a medical query router. Read the question below and decide which knowledge source is most appropriate.

Question: "{state['query']}"

Choose exactly one:
- medical_knowledge: General medical knowledge — conditions, symptoms, diagnoses, treatments, medications, pathophysiology
- device_manual: Medical equipment and devices — named devices, implants, scanners, monitors, pumps, and their indications, contraindications, or operation
- web_search: Anything requiring current information — recent guidelines, news, drug approvals, or data not covered by the above

Reply with only the option name, nothing else."""

    decision = get_llm_response(prompt, temperature=0).strip()
    valid = {"medical_knowledge", "device_manual", "web_search"}
    state["routed_to"] = decision if decision in valid else "web_search"
    state["source"] = state["routed_to"]
    state["routing_reason"] = f"Routed to {state['routed_to']}"
    logger.info(f"Router decision: {state['routed_to']}")
    return state


def route_decision(state: GraphState) -> str:
    return state["routed_to"]


def retrieve_clinical(state: GraphState) -> GraphState:
    try:
        docs = query_qna(state["query"])
        state["context"] = "\n".join(docs)
        state["source"] = "Medical Q&A Collection"
        logger.info(f"Retrieved {len(docs)} clinical docs")
        return state
    except Exception as e:
        logger.error(f"Clinical retrieval error: {e}")
        state["context"] = ""
        return state


def retrieve_device(state: GraphState) -> GraphState:
    try:
        docs = query_device(state["query"])
        state["context"] = "\n".join(docs)
        state["source"] = "Medical Device Manual"
        logger.info(f"Retrieved {len(docs)} device docs")
        return state
    except Exception as e:
        logger.error(f"Device retrieval error: {e}")
        state["context"] = ""
        return state


def web_search(state: GraphState) -> GraphState:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(state["query"], max_results=3))
        state["context"] = "\n".join(r["body"] for r in results) if results else "No results found"
        state["source"] = "Web Search (DuckDuckGo)"
        logger.info("Web search completed")
        return state
    except Exception as e:
        logger.error(f"Web search error: {e}")
        state["context"] = f"Search error: {e}"
        state["source"] = "Web Search (failed)"
        return state


def check_relevance(state: GraphState) -> GraphState:
    prompt = f"""Does the context below contain information that helps answer the question? Answer Yes if it is at least partially relevant. Answer No only if it is completely off-topic.

Context: {state['context'][:600]}
Question: {state['query']}

Answer with one word only: Yes or No"""

    try:
        decision = get_llm_response(prompt, temperature=0).strip()
        is_relevant = decision.lower().startswith("y")
        state["is_relevant"] = "Yes" if is_relevant else "No"
        state["relevance_reason"] = f"Context relevance: {state['is_relevant']}"

        count = state.get("iteration_count", 0) + 1
        state["iteration_count"] = count

        if count >= MAX_ITERATIONS:
            logger.info(f"Max iterations ({MAX_ITERATIONS}) reached — proceeding with best available context")
            state["is_relevant"] = "Yes"

        return state
    except Exception as e:
        logger.error(f"Relevance check error: {e}")
        state["is_relevant"] = "Yes"
        return state


def relevance_decision(state: GraphState) -> str:
    return state["is_relevant"]


def _build_history_block(history: List[dict]) -> str:
    if not history:
        return ""
    lines = ["Previous conversation:"]
    for turn in history:
        role = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{role}: {turn['content']}")
    return "\n".join(lines) + "\n\n"


def augment(state: GraphState) -> GraphState:
    history_block = _build_history_block(state.get("history", []))
    context = state["context"].strip()
    context_block = f"Retrieved context:\n{context}" if context else "No relevant context was retrieved."
    state["prompt"] = f"""{history_block}You are a knowledgeable medical assistant. Use the retrieved context as your primary source. Supplement with accurate medical knowledge where the context falls short. Keep your response concise and under 120 words.

{context_block}

Question: {state['query']}

Answer:"""
    return state


def generate(state: GraphState) -> GraphState:
    try:
        state["response"] = get_llm_response(state["prompt"])
        state["confidence"] = compute_confidence(state)
        logger.info(f"Answer generated (confidence: {state['confidence']:.0%})")
        return state
    except Exception as e:
        logger.error(f"Generation error: {e}")
        state["response"] = f"Error generating response: {e}"
        state["confidence"] = 0.0
        return state
