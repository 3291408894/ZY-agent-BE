"""
AI Agent API 测试 (PBI_04, PBI_12)

注意: Agent 所有端点在未登录时需返回 401/403。
完整的对话流程测试需要先实现认证模块 (PBI_01)。
"""

import pytest


@pytest.mark.asyncio
async def test_agent_chat_requires_auth(client):
    """POST /agent/chat — 未认证时返回 403（因 HTTPBearer auto_error=False 但 deps 抛 401）"""
    response = await client.post("/api/v1/agent/chat", json={
        "session_id": None,
        "message": "帮我总结《背影》",
    })
    # 没有 token 时 get_current_user 抛 401
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_sessions_requires_auth(client):
    """GET /agent/sessions — 未认证时返回 401"""
    response = await client.get("/api/v1/agent/sessions")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_session_messages_requires_auth(client):
    """GET /agent/sessions/{id} — 未认证时返回 401"""
    response = await client.get("/api/v1/agent/sessions/nonexistent-id")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_delete_session_requires_auth(client):
    """DELETE /agent/sessions/{id} — 未认证时返回 401"""
    response = await client.delete("/api/v1/agent/sessions/nonexistent-id")
    assert response.status_code in (401, 403)


# ================================================================
# 以下测试需要在认证模块 (PBI_01) 完成后激活
# 届时需要:
#   1. 注册用户 → 获取 access_token
#   2. 在请求头中携带 Authorization: Bearer <token>
# ================================================================

# @pytest.mark.asyncio
# async def test_create_session_and_chat(client):
#     """完整对话流程测试（需认证模块）"""
#     # TODO: 认证模块完成后实现
#     pass
