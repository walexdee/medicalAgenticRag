"""
Medical Agentic RAG – Production Backend
=========================================
FastAPI server with LangGraph-powered retrieval, routing, and generation.
"""

import os
import logging
import json
import asyncio
from collections import defaultdict
from typing import Optional, List
from datetime import datetime
from functools import lru_cache

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

import chromadb
from chromadb import EmbeddingFunction, Embeddings
from openai import OpenAI
from duckduckgo_search import DDGS
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

# =====================================================================
# Configuration
# =====================================================================
load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not set in .env file")

LLM_MODEL: str = "gpt-4o-mini"
EMBED_MODEL: str = "text-embedding-3-small"
CHROMA_PATH: str = "./chroma_db"
N_RESULTS: int = 5
MAX_ITERATIONS: int = 3
MAX_HISTORY_TURNS: int = 10
API_VERSION: str = "1.0.0"

# =====================================================================
# Logging Setup
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# =====================================================================
# Conversation Store (in-memory)
# =====================================================================
_conversation_store: dict = defaultdict(list)


def get_history(conversation_id: Optional[str]) -> List[dict]:
    if not conversation_id:
        return []
    return _conversation_store[conversation_id][-MAX_HISTORY_TURNS * 2:]


def save_turn(conversation_id: Optional[str], user_msg: str, assistant_msg: str):
    if not conversation_id:
        return
    store = _conversation_store[conversation_id]
    store.append({"role": "user", "content": user_msg})
    store.append({"role": "assistant", "content": assistant_msg})
    # Trim to max turns
    if len(store) > MAX_HISTORY_TURNS * 2:
        _conversation_store[conversation_id] = store[-(MAX_HISTORY_TURNS * 2):]


# =====================================================================
# Models & Schemas
# =====================================================================
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    conversation_id: Optional[str] = None


class SourceInfo(BaseModel):
    routing: str
    reason: str


class RelevanceInfo(BaseModel):
    is_relevant: bool
    reason: Optional[str] = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    source: str
    source_info: SourceInfo
    relevance: RelevanceInfo
    context: str
    iteration_count: int
    confidence: float
    timestamp: str
    conversation_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    models: dict
    databases: dict


class GraphState(TypedDict):
    query: str
    context: str
    prompt: str
    response: str
    source: str
    source_routing: str
    source_reason: str
    is_relevant: str
    relevance_reason: Optional[str]
    iteration_count: int
    history: List[dict]
    confidence: float


# =====================================================================
# OpenAI Client & Embedding Function
# =====================================================================
_openai_client = OpenAI(api_key=OPENAI_API_KEY)


def get_llm_response(prompt: str) -> str:
    """Call gpt-4o-mini and return the text response."""
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


class OpenAIEmbeddingFunction(EmbeddingFunction):
    """ChromaDB EmbeddingFunction backed by OpenAI text-embedding-3-small."""

    def __call__(self, input: List[str]) -> Embeddings:
        try:
            response = _openai_client.embeddings.create(
                model=EMBED_MODEL,
                input=input,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Embedding Error: {str(e)}")
            raise


_embed_fn = OpenAIEmbeddingFunction()

# =====================================================================
# Vector Store – ChromaDB
# =====================================================================
@lru_cache(maxsize=1)
def get_chroma_client():
    """Initialize ChromaDB client (cached)."""
    return chromadb.PersistentClient(path=CHROMA_PATH)


def get_collections():
    """Get or create ChromaDB collections."""
    client = get_chroma_client()
    qna = client.get_or_create_collection(
        name="medical_q_n_a",
        embedding_function=_embed_fn,
    )
    device = client.get_or_create_collection(
        name="medical_device_manual",
        embedding_function=_embed_fn,
    )
    return qna, device


def ingest_data(
    qa_csv: str = "medical_q_n_a.csv",
    device_csv: str = "medical_device_manuals_dataset.csv",
    sample_size: int = 500,
) -> dict:
    """
    Load CSVs and ingest into ChromaDB.
    Returns: {qa_count, device_count}
    """
    try:
        qna_coll, dev_coll = get_collections()
        counts = {"qa": 0, "device": 0}

        # Q&A ingestion
        if os.path.exists(qa_csv):
            df_qa = pd.read_csv(qa_csv).sample(
                min(sample_size, len(pd.read_csv(qa_csv))), random_state=42
            )
            df_qa["combined_text"] = (
                "Q: " + df_qa["Question"].astype(str) + " | "
                "A: " + df_qa["Answer"].astype(str) + " | "
                "Type: " + df_qa.get("qtype", "General").astype(str)
            )
            qna_coll.upsert(
                documents=df_qa["combined_text"].tolist(),
                metadatas=df_qa.to_dict(orient="records"),
                ids=df_qa.index.astype(str).tolist(),
            )
            counts["qa"] = len(df_qa)
            logger.info(f"Ingested {counts['qa']} Q&A records")

        # Device ingestion
        if os.path.exists(device_csv):
            df_dev = pd.read_csv(device_csv).sample(
                min(sample_size, len(pd.read_csv(device_csv))), random_state=42
            )
            df_dev["combined_text"] = (
                "Device: " + df_dev.get("Device_Name", "Unknown").astype(str) + " | "
                "Model: " + df_dev.get("Model_Number", "N/A").astype(str) + " | "
                "Indications: " + df_dev.get("Indications_for_Use", "N/A").astype(str)
            )
            dev_coll.upsert(
                documents=df_dev["combined_text"].tolist(),
                metadatas=df_dev.to_dict(orient="records"),
                ids=df_dev.index.astype(str).tolist(),
            )
            counts["device"] = len(df_dev)
            logger.info(f"Ingested {counts['device']} Device records")

        return counts
    except Exception as e:
        logger.error(f"Data ingestion error: {str(e)}")
        raise


# =====================================================================
# Web Search
# =====================================================================
WEB_SEARCH_ENABLED = True


# =====================================================================
# LangGraph Nodes
# =====================================================================
def router_node(state: GraphState) -> GraphState:
    """LLM-based router to decide retrieval path."""
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
    """Retrieve from Q&A collection."""
    try:
        qna_coll, _ = get_collections()
        results = qna_coll.query(query_texts=[state["query"]], n_results=N_RESULTS)
        state["context"] = "\n".join(results["documents"][0]) if results["documents"] else ""
        state["source"] = "Medical Q&A Collection"
        logger.info(f"Retrieved {len(results['documents'][0])} Q&A docs")
        return state
    except Exception as e:
        logger.error(f"Q&A retrieval error: {str(e)}")
        state["context"] = ""
        return state


def retrieve_device(state: GraphState) -> GraphState:
    """Retrieve from Device collection."""
    try:
        _, dev_coll = get_collections()
        results = dev_coll.query(query_texts=[state["query"]], n_results=N_RESULTS)
        state["context"] = "\n".join(results["documents"][0]) if results["documents"] else ""
        state["source"] = "Medical Device Manual"
        logger.info(f"Retrieved {len(results['documents'][0])} Device docs")
        return state
    except Exception as e:
        logger.error(f"Device retrieval error: {str(e)}")
        state["context"] = ""
        return state


def web_search_node(state: GraphState) -> GraphState:
    """Fallback web search using DuckDuckGo."""
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
    """Check if retrieved context is relevant."""
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
    """Format conversation history for inclusion in prompt."""
    if not history:
        return ""
    lines = ["Previous conversation:"]
    for turn in history:
        role = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{role}: {turn['content']}")
    return "\n".join(lines) + "\n\n"


def augment_node(state: GraphState) -> GraphState:
    """Build RAG prompt with optional conversation history."""
    history_block = _build_history_block(state.get("history", []))
    context = state["context"].strip()
    context_block = f"Retrieved context:\n{context}" if context else "No relevant context was retrieved."
    state["prompt"] = f"""{history_block}You are a knowledgeable medical assistant. Use the retrieved context as your primary source. If the context does not sufficiently cover the question, supplement your answer with accurate medical knowledge. Keep the response concise (under 120 words).

{context_block}

Question: {state['query']}

Answer:"""
    return state


def _compute_confidence(state: GraphState) -> float:
    """
    Heuristic confidence score based on pipeline outcomes.
    Source quality + relevance + iteration penalty.
    """
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
        base = 0.40  # failed web search or unknown

    if not is_relevant:
        base -= 0.15

    # Each extra iteration beyond the first indicates retrieval difficulty
    base -= max(0, iterations - 1) * 0.08

    return round(max(0.0, min(1.0, base)), 2)


def generate_node(state: GraphState) -> GraphState:
    """Generate final answer."""
    try:
        state["response"] = get_llm_response(state["prompt"])
        state["confidence"] = _compute_confidence(state)
        logger.info(f"Answer generated (confidence: {state['confidence']:.0%})")
        return state
    except Exception as e:
        logger.error(f"Generation error: {str(e)}")
        state["response"] = f"Error generating response: {str(e)}"
        state["confidence"] = 0.0
        return state


# =====================================================================
# Build LangGraph Workflow
# =====================================================================
@lru_cache(maxsize=1)
def build_agentic_rag():
    """Build and compile the LangGraph workflow (cached)."""
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("Router", router_node)
    workflow.add_node("Retrieve_QnA", retrieve_qna)
    workflow.add_node("Retrieve_Device", retrieve_device)
    workflow.add_node("Web_Search", web_search_node)
    workflow.add_node("Relevance_Checker", relevance_checker)
    workflow.add_node("Augment", augment_node)
    workflow.add_node("Generate", generate_node)

    # Add edges
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
        {
            "Yes": "Augment",
            "No": "Web_Search",
        },
    )
    workflow.add_edge("Augment", "Generate")
    workflow.add_edge("Generate", END)

    logger.info("LangGraph workflow compiled")
    return workflow.compile()


def query_rag(question: str, history: Optional[List[dict]] = None) -> dict:
    """Execute the agentic RAG pipeline."""
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


def run_pipeline_for_context(question: str, history: Optional[List[dict]] = None) -> GraphState:
    """
    Run Router → Retrieve → Relevance → Augment nodes to build the prompt,
    but skip Generate so we can stream the answer separately.
    """
    # We reuse query_rag but it runs generate_node too; we just ignore the
    # pre-generated response and use the prompt for streaming below.
    return query_rag(question, history)


async def stream_rag_response(question: str, history: Optional[List[dict]] = None):
    """
    Async generator that yields SSE-formatted events:
      - {"type":"meta", "source":..., "source_info":..., "relevance":..., ...}
      - {"type":"token", "token":"..."}
      - {"type":"done", "iteration_count":..., "timestamp":...}
      - {"type":"error", "message":"..."}
    """
    try:
        # Run full pipeline in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        state = await loop.run_in_executor(None, run_pipeline_for_context, question, history)

        # Emit metadata first
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

        # Stream the generation token-by-token using OpenAI streaming
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

        # Emit done event with heuristic confidence
        done = {
            "type": "done",
            "answer": full_response.strip(),
            "confidence": _compute_confidence(state),
            "iteration_count": state["iteration_count"],
            "timestamp": datetime.utcnow().isoformat(),
        }
        yield f"data: {json.dumps(done)}\n\n"

    except Exception as e:
        logger.error(f"Stream error: {str(e)}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


# =====================================================================
# FastAPI App
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager."""
    logger.info("Starting Medical Agentic RAG Backend")
    try:
        get_chroma_client()
        logger.info("ChromaDB connected")
    except Exception as e:
        logger.error(f"ChromaDB initialization failed: {str(e)}")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Medical Agentic RAG",
    description="Production-grade medical knowledge system with routing and relevance checking",
    version=API_VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# API Endpoints
# =====================================================================
@app.post("/api/query", response_model=QueryResponse)
async def api_query(request: QueryRequest):
    """Main RAG query endpoint (non-streaming)."""
    logger.info(f"Query received: {request.query[:50]}...")

    try:
        history = get_history(request.conversation_id)
        result = query_rag(request.query, history)
        answer = result["response"]

        # Persist turn
        save_turn(request.conversation_id, request.query, answer)

        return QueryResponse(
            query=result["query"],
            answer=answer,
            source=result["source"],
            source_info=SourceInfo(
                routing=result["source_routing"],
                reason=result["source_reason"],
            ),
            relevance=RelevanceInfo(
                is_relevant=result["is_relevant"].lower() == "yes",
                reason=result["relevance_reason"],
            ),
            context=result["context"][:200],
            iteration_count=result["iteration_count"],
            confidence=result.get("confidence", 0.5),
            timestamp=datetime.utcnow().isoformat(),
            conversation_id=request.conversation_id,
        )
    except Exception as e:
        logger.error(f"Query error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}",
        )


@app.post("/api/query/stream")
async def api_query_stream(request: QueryRequest):
    """
    Streaming RAG query endpoint (SSE).
    Emits: meta -> token* -> done  (or error)
    """
    logger.info(f"Stream query received: {request.query[:50]}...")
    history = get_history(request.conversation_id)

    async def event_generator():
        full_answer = ""
        async for event in stream_rag_response(request.query, history):
            yield event
            # Capture the full answer from done event to save history
            if event.startswith("data: "):
                try:
                    payload = json.loads(event[6:])
                    if payload.get("type") == "done":
                        full_answer = payload.get("answer", "")
                except Exception:
                    pass
        if full_answer:
            save_turn(request.conversation_id, request.query, full_answer)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    qna_coll, dev_coll = get_collections()
    return HealthResponse(
        status="healthy",
        version=API_VERSION,
        models={
            "llm": LLM_MODEL,
            "embeddings": EMBED_MODEL,
        },
        databases={
            "chroma_path": CHROMA_PATH,
            "qa_collection_count": qna_coll.count(),
            "device_collection_count": dev_coll.count(),
        },
    )


@app.post("/api/ingest")
async def ingest(qa_csv: str = "medical_q_n_a.csv", sample_size: int = 500):
    """Ingest data into ChromaDB."""
    try:
        counts = ingest_data(qa_csv=qa_csv, sample_size=sample_size)
        logger.info(f"Data ingestion completed: {counts}")
        return {
            "status": "success",
            "qa_records": counts["qa"],
            "device_records": counts["device"],
        }
    except Exception as e:
        logger.error(f"Ingestion error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Medical Agentic RAG",
        "version": API_VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }


# =====================================================================
# Error Handlers
# =====================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
