"""
知识图谱相关 Pydantic Schema (PBI_11)
"""

from datetime import datetime

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # category / article / knowledge
    x: float = 0
    y: float = 0


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str


class GenerateGraphReq(BaseModel):
    source_type: str = Field(..., description="subject / chapter / file")
    source: str = Field(..., description="学科或章节名")
    file_id: str | None = None


class KnowledgeGraphResp(BaseModel):
    graph_id: str
    title: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class KnowledgeGraphItem(BaseModel):
    id: str
    title: str
    node_count: int = 0
    edge_count: int = 0
    source_type: str
    created_at: datetime


class RelatedNode(BaseModel):
    id: str
    label: str
    relation: str


class NodeDetailResp(BaseModel):
    node_id: str
    label: str
    description: str = ""
    examples: list[str] = []
    common_mistakes: list[str] = []
    related_nodes: list[RelatedNode] = []
