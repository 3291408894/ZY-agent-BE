"""
知识图谱相关 Pydantic Schema (PBI_11)
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════════════════════

class GraphSourceType(str, Enum):
    """图谱来源类型"""
    SUBJECT = "subject"    # 学科范围
    CHAPTER = "chapter"    # 教材章节
    FILE = "file"          # 上传文件


class NodeType(str, Enum):
    """图谱节点类型"""
    CATEGORY = "category"      # 分类/模块节点
    ARTICLE = "article"        # 课文/章节节点
    KNOWLEDGE = "knowledge"    # 知识点节点


# ═══════════════════════════════════════════════════════════
# 图谱节点 & 边
# ═══════════════════════════════════════════════════════════

class GraphNode(BaseModel):
    """知识图谱节点"""
    id: str = Field(..., description="节点唯一标识，如 n1, n2")
    label: str = Field(..., description="节点显示文本")
    type: str = Field(..., description="节点类型：category / article / knowledge")
    x: float = Field(default=0, description="画布 X 坐标")
    y: float = Field(default=0, description="画布 Y 坐标")


class GraphEdge(BaseModel):
    """知识图谱边"""
    source: str = Field(..., description="起始节点 ID")
    target: str = Field(..., description="目标节点 ID")
    relation: str = Field(..., description="关系描述，如'包含'、'重点考查'、'关联'")


# ═══════════════════════════════════════════════════════════
# 请求模型
# ═══════════════════════════════════════════════════════════

class GenerateGraphReq(BaseModel):
    """生成知识图谱请求 (POST /knowledge/graph)"""
    source_type: str = Field(
        ...,
        description="来源类型：subject=学科范围, chapter=教材章节, file=上传文件"
    )
    source: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="学科或章节名称，如'语文-七年级-文言文'"
    )
    file_id: str | None = Field(
        default=None,
        description="文件ID（source_type=file 时传入）"
    )


# ═══════════════════════════════════════════════════════════
# 响应模型 — 图谱
# ═══════════════════════════════════════════════════════════

class KnowledgeGraphResp(BaseModel):
    """生成图谱响应"""
    graph_id: str = Field(..., description="图谱 ID")
    title: str = Field(..., description="图谱标题")
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    source_type: str = Field(..., description="来源类型")
    created_at: datetime | None = None


class KnowledgeGraphItem(BaseModel):
    """图谱列表项（简要信息）"""
    id: str
    title: str
    node_count: int = 0
    edge_count: int = 0
    source_type: str
    node_count: int = Field(default=0, description="节点数量")
    edge_count: int = Field(default=0, description="边数量")
    created_at: datetime


<<<<<<< HEAD
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
=======
class KnowledgeGraphListResponse(BaseModel):
    """图谱分页列表响应"""
    items: list[KnowledgeGraphItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ═══════════════════════════════════════════════════════════
# 响应模型 — 节点详情
# ═══════════════════════════════════════════════════════════

class ExampleQuestion(BaseModel):
    """典型例题"""
    question: str = Field(..., description="题目内容")
    answer: str = Field(..., description="参考答案")


class CommonMistake(BaseModel):
    """常见易错点"""
    mistake: str = Field(..., description="常见错误描述")
    correction: str = Field(..., description="纠正建议")


class NodeDetailResponse(BaseModel):
    """节点详情响应"""
    node_id: str = Field(..., description="节点 ID")
    label: str = Field(..., description="节点标签")
    node_type: str = Field(..., description="节点类型")
    graph_id: str = Field(..., description="所属图谱 ID")
    graph_title: str = Field(..., description="所属图谱标题")
    summary: str = Field(default="", description="知识点概述")
    key_points: list[str] = Field(default_factory=list, description="核心要点")
    example_questions: list[ExampleQuestion] = Field(default_factory=list, description="典型例题")
    common_mistakes: list[CommonMistake] = Field(default_factory=list, description="常见易错点")
    related_knowledge: list[str] = Field(default_factory=list, description="关联知识点")


# ═══════════════════════════════════════════════════════════
# 响应模型 — 导出
# ═══════════════════════════════════════════════════════════

class ExportFormat(str, Enum):
    """导出格式"""
    PNG = "png"
    SVG = "svg"
    PDF = "pdf"


class ExportRequest(BaseModel):
    """导出请求"""
    format: ExportFormat = Field(default=ExportFormat.PNG, description="导出格式")
    width: int = Field(default=1200, ge=400, le=4000, description="导出宽度")
    height: int = Field(default=900, ge=300, le=3000, description="导出高度")
    background: str = Field(default="#ffffff", description="背景色")
    include_title: bool = Field(default=True, description="是否包含标题")
>>>>>>> main
