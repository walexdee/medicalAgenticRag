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


def get_llm_response(prompt: str) -> str:
    try:
        response = _openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM Error: {str(e)}")
        raise


def router_node(state: GraphState) -> GraphState:
    prompt = f"""You are a medical routing agent.

Query: "{state['query']}"

Route to ONE option:
- Retrieve_QnA: Medical conditions, symptoms, treatments, diseases
- Retrieve_Device: Medical devices, device manuals, usage, specifications
- Web_Search: Current news, recent events, prices, external data

Respond ONLY with: Retrieve_QnA, Retrieve_Device, or Web_Search"""

    decision = get_llm_response(prompt).strip()
    valid = {"Retrieve_QnA", "Retrieve_Device", "Web_Search"}
    state["source"] = decision if decision in valid else "Web_Search"
    state["source_routing"] = state["source"]
    state["source_reason"] = f"Routed to {state['source_routing']}"
    logger.info(f"Router decision: {state['source']}")
    return state


def route_decision(state: GraphState) -> str:
    return state["source"]


def retrieve_qna(state: GraphState) -> GraphState:
    try:
        docs = query_qna(state["query"])
        state["context"] = "\n".join(docs)
        state["source"] = "Medical Q&A Collection"
        logger.info(f"Retrieved {len(docs)} Q&A docs")
        return state
    except Exception as e:
        logger.error(f"Q&A retrieval error: {str(e)}")
        state["context"] = ""
        return state


def retrieve_device(state: GraphState) -> GraphState:
    try:
        docs = query_device(state["query"])
        state["context"] = "\n".join(docs)
        state["source"] = "Medical Device Manual"
        logger.info(f"Retrieved {len(docs)} Device docs")
        return state
    except Exception as e:
        logger.error(f"Device retrieval error: {str(e)}")
        state["context"] = ""
        return state


def web_search_node(state: GraphState) -> GraphState:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(state["query"], max_results=3))
        state["context"] = "\n".join(r["body"] for r in results) if results else "No results found"
        state["source"] = "Web Search (DuckDuckGo)"
        logger.info("Web search completed")
        return state
    except Exception as e:
        logger.error(f"Web search error: {str(e)}")
        state["context"] = f"Search error: {str(e)}"
        state["source"] = "Web Search (failed)"
        return state


def relevance_checker(state: GraphState) -> GraphState:
    prompt = f"""Does the following context contain information that helps answer the user's query? Answer Yes if it is even partially relevant or covers the topic. Answer No only if it is completely unrelated.

Context: {state['context'][:600]}
Query: {state['query']}

Answer ONLY with the single word: Yes or No"""

    try:
        decision = get_llm_response(prompt).strip()
        is_relevant = decision.lower().startswith("y")
        state["is_relevant"] = "Yes" if is_relevant else "No"
        state["relevance_reason"] = f"Context relevance: {state['is_relevant']}"

        count = state.get("iteration_count", 0) + 1
        state["iteration_count"] = count

        if count >= MAX_ITERATIONS:
            logger.info(f"Max iterations ({MAX_ITERATIONS}) reached")
            state["is_relevant"] = "Yes"

        return state
    except Exception as e:
        logger.error(f"Relevance check error: {str(e)}")
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


def augment_node(state: GraphState) -> GraphState:
    history_block = _build_history_block(state.get("history", []))
    context = state["context"].strip()
    context_block = f"Retrieved context:\n{context}" if context else "No relevant context was retrieved."
    state["prompt"] = f"""{history_block}You are a knowledgeable medical assistant. Use the retrieved context as your primary source. If the context does not sufficiently cover the question, supplement your answer with accurate medical knowledge. Keep the response concise (under 120 words).

{context_block}

Question: {state['query']}

Answer:"""
    return state


def generate_node(state: GraphState) -> GraphState:
    try:
        state["response"] = get_llm_response(state["prompt"])
        state["confidence"] = compute_confidence(state)
        logger.info(f"Answer generated (confidence: {state['confidence']:.0%})")
        return state
    except Exception as e:
        logger.error(f"Generation error: {str(e)}")
        state["response"] = f"Error generating response: {str(e)}"
        state["confidence"] = 0.0
        return state
