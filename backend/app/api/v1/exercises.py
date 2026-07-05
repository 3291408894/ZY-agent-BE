"""
习题路由 (PBI_08, PBI_09, PBI_10) — 生成、提交、批改

TODO: Sprint 2 实现
"""

from fastapi import APIRouter

router = APIRouter()

# POST   /exercises/generate              — 生成习题 [SSE]
# POST   /exercises/grade                  — 提交作答/批改
# GET    /exercises/history                — 做题历史
# GET    /exercises/batches/{batch_id}     — 单次练习详情
# DELETE /exercises/batches/{batch_id}     — 删除
