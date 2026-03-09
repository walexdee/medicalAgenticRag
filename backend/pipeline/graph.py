import asyncio
import json
import logging
from datetime import datetime
from functools import lru_cache
from typing import Optional, List

from openai import OpenAI
from langgraph.graph import StateGraph, START, END

from backend.config import OPENAI_API_KEY, LLM_MODEL
from backend.models import GraphState
from backend.pipeline.nodes import (
    router_node, route_decision,
    retrieve_clinical, retrieve_device, web_search,
    check_relevance, relevance_decision,
    augment, generate,
)
from backend.pipeline.state import compute_confidence

logger = logging.getLogger(__name__)

_openai_client = OpenAI(api_key=OPENAI_API_KEY)


@lru_cache(maxsize=1)
def build_agentic_rag():
    """Build and compile the LangGraph pipeline (cached for the process lifetime)."""
    workflow = StateGraph(GraphState)

    workflow.add_node("router",            router_node)
    workflow.add_node("retrieve_clinical", retrieve_clinical)
    workflow.add_node("retrieve_device",   retrieve_device)
    workflow.add_node("web_search",        web_search)
    workflow.add_node("relevance_check",   check_relevance)
    workflow.add_node("augment",           augment)
    workflow.add_node("generate",          generate)

    workflow.add_edge(START, "router")
    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "medical_knowledge": "retrieve_clinical",
            "device_manual": "retrieve_device",
            "web_search":    "web_search",
        },
    )
    workflow.add_edge("retrieve_clinical", "relevance_check")
    workflow.add_edge("retrieve_device",   "relevance_check")
    workflow.add_edge("web_search",        "relevance_check")
    workflow.add_conditional_edges(
        "relevance_check",
        relevance_decision,
        {"Yes": "augment", "No": "web_search"},
    )
    workflow.add_edge("augment",  "generate")
    workflow.add_edge("generate", END)

    logger.info("LangGraph pipeline compiled")
    return workflow.compile()


def query_rag(question: str, history: Optional[List[dict]] = None) -> dict:
    graph = build_agentic_rag()
    initial_state: GraphState = {
        "query": question,
        "context": "",
        "prompt": "",
        "response": "",
        "source": "",
        "routed_to":      "",
        "routing_reason": "",
        "is_relevant": "",
        "relevance_reason": None,
        "iteration_count": 0,
        "history": history or [],
        "confidence": 0.0,
    }
    result = graph.invoke(initial_state)
    logger.info(f"Query completed: {question[:50]}...")
    return result


async def stream_rag_response(question: str, history: Optional[List[dict]] = None):
    """Async generator yielding SSE events: meta → token* → done (or error)."""
    try:
        loop = asyncio.get_running_loop()
        state = await loop.run_in_executor(None, query_rag, question, history)

        meta = {
            "type": "meta",
            "source": state["source"],
            "source_info": {
                "routing": state["routed_to"],
                "reason":  state["routing_reason"],
            },
            "relevance": {
                "is_relevant": state["is_relevant"].lower() == "yes",
                "reason": state["relevance_reason"],
            },
            "context": state["context"][:200],
        }
        yield f"data: {json.dumps(meta)}\n\n"

        full_response = ""
        stream = _openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": state["prompt"]}],
            temperature=0.5,
            max_tokens=500,
            stream=True,
        )
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

        done = {
            "type": "done",
            "answer": full_response.strip(),
            "confidence": compute_confidence(state),
            "iteration_count": state["iteration_count"],
            "timestamp": datetime.utcnow().isoformat(),
        }
        yield f"data: {json.dumps(done)}\n\n"

    except Exception as e:
        logger.error(f"Stream error: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
