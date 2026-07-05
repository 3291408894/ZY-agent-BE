"""
文件管理路由 (PBI_05) — 上传、解析、状态查询

TODO: Sprint 2 实现
"""

from fastapi import APIRouter

router = APIRouter()

# POST   /files/upload          — 上传文件
# GET    /files                 — 文件列表
# GET    /files/{id}/status     — 解析状态
# POST   /files/{id}/reparse    — 重新解析
# DELETE /files/{id}            — 删除文件
