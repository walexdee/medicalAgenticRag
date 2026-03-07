from typing import Optional, List
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


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
