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
    retrieve_qna, retrieve_device, web_search_node,
    relevance_checker, relevance_decision,
    augment_node, generate_node,
)
from backend.pipeline.state import compute_confidence

logger = logging.getLogger(__name__)

_openai_client = OpenAI(api_key=OPENAI_API_KEY)


@lru_cache(maxsize=1)
def build_agentic_rag():
    """Build and compile the LangGraph workflow (cached)."""
    workflow = StateGraph(GraphState)

    workflow.add_node("Router", router_node)
    workflow.add_node("Retrieve_QnA", retrieve_qna)
    workflow.add_node("Retrieve_Device", retrieve_device)
    workflow.add_node("Web_Search", web_search_node)
    workflow.add_node("Relevance_Checker", relevance_checker)
    workflow.add_node("Augment", augment_node)
    workflow.add_node("Generate", generate_node)

    workflow.add_edge(START, "Router")
    workflow.add_conditional_edges(
        "Router",
        route_decision,
        {
            "Retrieve_QnA": "Retrieve_QnA",
            "Retrieve_Device": "Retrieve_Device",
            "Web_Search": "Web_Search",
        },
    )
    workflow.add_edge("Retrieve_QnA", "Relevance_Checker")
    workflow.add_edge("Retrieve_Device", "Relevance_Checker")
    workflow.add_edge("Web_Search", "Relevance_Checker")
    workflow.add_conditional_edges(
        "Relevance_Checker",
        relevance_decision,
        {"Yes": "Augment", "No": "Web_Search"},
    )
    workflow.add_edge("Augment", "Generate")
    workflow.add_edge("Generate", END)

    logger.info("LangGraph workflow compiled")
    return workflow.compile()


def query_rag(question: str, history: Optional[List[dict]] = None) -> dict:
    graph = build_agentic_rag()
    initial_state: GraphState = {
        "query": question,
        "context": "",
        "prompt": "",
        "response": "",
        "source": "",
        "source_routing": "",
        "source_reason": "",
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
                "routing": state["source_routing"],
                "reason": state["source_reason"],
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
