"""
Agentic RAG – Medical Knowledge System
=======================================
Architecture (LangGraph StateGraph):

  START → Router → Retrieve_QnA ──────────────┐
               ├── Retrieve_Device ────────────┼──→ Relevance_Checker → Augment → Generate → END
               └── Web_Search ────────────────┘         │
                        ↑                               (No)
                        └───────────────────────────────┘

Tools / Models
--------------
  LLM        : gpt-4o-mini  (router, relevance-check, generation)
  Embeddings : text-embedding-3-small  (OpenAI, via ChromaDB custom function)
  Vector DB  : ChromaDB  (persistent, 2 collections)
  Web Search : DuckDuckGo (free, no API key required)

Required environment variables (.env):
  OPENAI_API_KEY
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import os
import pandas as pd
from typing import List, Literal
from typing_extensions import TypedDict
from dotenv import load_dotenv

import chromadb
from chromadb import EmbeddingFunction, Embeddings
from openai import OpenAI
from duckduckgo_search import DDGS
from langgraph.graph import StateGraph, START, END

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

LLM_MODEL: str = "gpt-4o-mini"
EMBED_MODEL: str = "text-embedding-3-small"
CHROMA_PATH: str = "./chroma_db"
N_RESULTS: int = 3
MAX_ITERATIONS: int = 3

# ---------------------------------------------------------------------------
# OpenAI helpers
# ---------------------------------------------------------------------------
_openai_client = OpenAI(api_key=OPENAI_API_KEY)


def get_llm_response(prompt: str) -> str:
    """Call gpt-4o-mini and return the text response."""
    response = _openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# OpenAI Embedding Function for ChromaDB
# ---------------------------------------------------------------------------
class OpenAIEmbeddingFunction(EmbeddingFunction):
    """Drop-in ChromaDB EmbeddingFunction backed by OpenAI text-embedding-3-small."""

    def __call__(self, input: List[str]) -> Embeddings:
        response = _openai_client.embeddings.create(
            model=EMBED_MODEL,
            input=input,
        )
        return [item.embedding for item in response.data]


_embed_fn = OpenAIEmbeddingFunction()

# ---------------------------------------------------------------------------
# Vector Store – ChromaDB (2 collections)
# ---------------------------------------------------------------------------
_chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

collection_qna = _chroma_client.get_or_create_collection(
    name="medical_q_n_a",
    embedding_function=_embed_fn,
)
collection_device = _chroma_client.get_or_create_collection(
    name="medical_device_manual",
    embedding_function=_embed_fn,
)


def ingest_data(
    qa_csv: str = "medical_q_n_a.csv",
    device_csv: str = "medical_device_manuals_dataset.csv",
    sample_size: int = 500,
    random_state: int = 0,
) -> None:
    """
    Load CSVs, prepare combined-text columns, and upsert into ChromaDB.
    Safe to call multiple times (get_or_create + upsert).
    """
    # --- Medical Q&A ---
    df_qa = pd.read_csv(qa_csv).sample(sample_size, random_state=random_state).reset_index(drop=True)
    df_qa["combined_text"] = (
        "Question: " + df_qa["Question"].astype(str) + ". "
        + "Answer: " + df_qa["Answer"].astype(str) + ". "
        + "Type: " + df_qa["qtype"].astype(str) + ". "
    )
    collection_qna.upsert(
        documents=df_qa["combined_text"].tolist(),
        metadatas=df_qa.to_dict(orient="records"),
        ids=df_qa.index.astype(str).tolist(),
    )
    print(f"✅  Ingested {len(df_qa)} Medical Q&A records.")

    # --- Medical Device Manuals ---
    df_dev = (
        pd.read_csv(device_csv)
        .sample(sample_size, random_state=random_state)
        .reset_index(drop=True)
    )
    df_dev["combined_text"] = (
        "Device Name: " + df_dev["Device_Name"].astype(str) + ". "
        + "Model: " + df_dev["Model_Number"].astype(str) + ". "
        + "Manufacturer: " + df_dev["Manufacturer"].astype(str) + ". "
        + "Indications: " + df_dev["Indications_for_Use"].astype(str) + ". "
        + "Contraindications: " + df_dev["Contraindications"].fillna("None").astype(str)
    )
    collection_device.upsert(
        documents=df_dev["combined_text"].tolist(),
        metadatas=df_dev.to_dict(orient="records"),
        ids=df_dev.index.astype(str).tolist(),
    )
    print(f"✅  Ingested {len(df_dev)} Medical Device records.")




# ---------------------------------------------------------------------------
# LangGraph – State Definition
# ---------------------------------------------------------------------------
class GraphState(TypedDict):
    query: str
    context: str
    prompt: str
    response: str
    source: str           # Which tool was selected by the router
    is_relevant: str      # "Yes" | "No"
    iteration_count: int


# ---------------------------------------------------------------------------
# Node: Router  (LLM-based)
# ---------------------------------------------------------------------------
def router_node(state: GraphState) -> GraphState:
    """Use the LLM to decide which retrieval path to take."""
    print("--- ROUTER ---")
    decision_prompt = f"""
You are a routing agent. Based on the user query, decide where to look for information.

Options:
- Retrieve_QnA: general medical knowledge, symptoms, diseases, or treatments.
- Retrieve_Device: medical devices, device manuals, or device usage instructions.
- Web_Search: recent news, current events, prices, tariffs, or any topic not covered by the local database.

Query: "{state['query']}"

Respond ONLY with one of: Retrieve_QnA, Retrieve_Device, Web_Search
"""
    decision = get_llm_response(decision_prompt)
    # Normalise – ensure only valid tokens pass through
    valid = {"Retrieve_QnA", "Retrieve_Device", "Web_Search"}
    if decision not in valid:
        decision = "Web_Search"  # safe fallback
    print(f"  → {decision}")
    state["source"] = decision
    return state


def route_decision(state: GraphState) -> str:
    return state["source"]


# ---------------------------------------------------------------------------
# Node: Retrievers
# ---------------------------------------------------------------------------
def retrieve_qna(state: GraphState) -> GraphState:
    print("--- RETRIEVE (Medical Q&A) ---")
    results = collection_qna.query(query_texts=[state["query"]], n_results=N_RESULTS)
    state["context"] = "\n".join(results["documents"][0])
    state["source"] = "Medical Q&A Collection"
    return state


def retrieve_device(state: GraphState) -> GraphState:
    print("--- RETRIEVE (Medical Device) ---")
    results = collection_device.query(query_texts=[state["query"]], n_results=N_RESULTS)
    state["context"] = "\n".join(results["documents"][0])
    state["source"] = "Medical Device Manual"
    return state


def web_search_node(state: GraphState) -> GraphState:
    print("--- WEB SEARCH ---")
    with DDGS() as ddgs:
        results = list(ddgs.text(state["query"], max_results=3))
    state["context"] = "\n".join(r["body"] for r in results) if results else "No results found"
    state["source"] = "Web Search (DuckDuckGo)"
    return state


# ---------------------------------------------------------------------------
# Node: Relevance Checker
# ---------------------------------------------------------------------------
def relevance_checker(state: GraphState) -> GraphState:
    print("--- RELEVANCE CHECKER ---")
    relevance_prompt = f"""
Check whether the context below is relevant to the user query.

####
Context:
{state['context']}
####
User Query: {state['query']}

Options:
- Yes: if the context is relevant.
- No: if the context is NOT relevant.

Please answer with only 'Yes' or 'No'.
"""
    decision = get_llm_response(relevance_prompt)
    # Normalise
    state["is_relevant"] = "Yes" if decision.lower().startswith("y") else "No"
    print(f"  → Relevant: {state['is_relevant']}")
    return state


def relevance_decision(state: GraphState) -> str:
    """Conditional edge: force 'Yes' after MAX_ITERATIONS to avoid infinite loops."""
    count = state.get("iteration_count", 0) + 1
    state["iteration_count"] = count
    if count >= MAX_ITERATIONS:
        print(f"  → Max iterations ({MAX_ITERATIONS}) reached – forcing answer.")
        return "Yes"
    return state["is_relevant"]


# ---------------------------------------------------------------------------
# Node: Augment (build RAG prompt)
# ---------------------------------------------------------------------------
def augment_node(state: GraphState) -> GraphState:
    print("--- AUGMENT ---")
    state["prompt"] = f"""
Answer the following question using only the context below.

Context:
{state['context']}

Question: {state['query']}

Please limit your answer to 50 words.
"""
    return state


# ---------------------------------------------------------------------------
# Node: Generate (LLM answer)
# ---------------------------------------------------------------------------
def generate_node(state: GraphState) -> GraphState:
    print("--- GENERATE ---")
    state["response"] = get_llm_response(state["prompt"])
    return state


# ---------------------------------------------------------------------------
# Build the LangGraph workflow
# ---------------------------------------------------------------------------
def build_agentic_rag() -> StateGraph:
    workflow = StateGraph(GraphState)

    # Nodes
    workflow.add_node("Router", router_node)
    workflow.add_node("Retrieve_QnA", retrieve_qna)
    workflow.add_node("Retrieve_Device", retrieve_device)
    workflow.add_node("Web_Search", web_search_node)
    workflow.add_node("Relevance_Checker", relevance_checker)
    workflow.add_node("Augment", augment_node)
    workflow.add_node("Generate", generate_node)

    # Edges
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
            "No": "Web_Search",   # fallback to web if local retrieval wasn't relevant
        },
    )
    workflow.add_edge("Augment", "Generate")
    workflow.add_edge("Generate", END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
def query(question: str, graph=None) -> dict:
    """
    Run a single question through the agentic RAG pipeline.

    Parameters
    ----------
    question : str
        The natural-language question to answer.
    graph : compiled LangGraph, optional
        Pass a pre-compiled graph to avoid rebuilding it on every call.

    Returns
    -------
    dict with keys: query, response, source, context
    """
    if graph is None:
        graph = build_agentic_rag()

    initial_state: GraphState = {
        "query": question,
        "context": "",
        "prompt": "",
        "response": "",
        "source": "",
        "is_relevant": "",
        "iteration_count": 0,
    }

    final_state = None
    for step in graph.stream(initial_state):
        for _node, state in step.items():
            final_state = state

    return {
        "query": question,
        "response": final_state.get("response", ""),
        "source": final_state.get("source", ""),
        "context": final_state.get("context", ""),
    }


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Medical Agentic RAG")
    parser.add_argument("--ingest", action="store_true", help="Ingest CSV data into ChromaDB")
    parser.add_argument("--qa-csv", default="medical_q_n_a.csv")
    parser.add_argument("--device-csv", default="medical_device_manuals_dataset.csv")
    parser.add_argument("--query", "-q", type=str, help="Ask a question")
    args = parser.parse_args()

    if args.ingest:
        ingest_data(qa_csv=args.qa_csv, device_csv=args.device_csv)

    if args.query:
        rag = build_agentic_rag()
        result = query(args.query, graph=rag)
        print("\n" + "=" * 60)
        print(f"Query   : {result['query']}")
        print(f"Source  : {result['source']}")
        print(f"Answer  : {result['response']}")
        print("=" * 60)
