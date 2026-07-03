"""
课文总结路由 (PBI_06) — 生成总结、历史记录

TODO: Sprint 1 实现
"""

from fastapi import APIRouter

router = APIRouter()

# POST   /summaries/generate  — 发起总结 [SSE]
# GET    /summaries           — 历史总结列表
# GET    /summaries/{id}      — 查看详情
# DELETE /summaries/{id}      — 删除
