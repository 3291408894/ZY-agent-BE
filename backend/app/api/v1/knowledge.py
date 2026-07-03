"""
知识图谱路由 (PBI_11) — 生成、查询、导出

TODO: Sprint 2 实现
"""

from fastapi import APIRouter

router = APIRouter()

# POST   /knowledge/graph                    — 生成知识图谱
# GET    /knowledge/graphs                   — 图谱列表
# GET    /knowledge/graphs/{id}              — 查看图谱
# GET    /knowledge/graphs/{id}/node/{nid}   — 节点详情
# DELETE /knowledge/graphs/{id}              — 删除图谱
# POST   /knowledge/graphs/{id}/export       — 导出图片
