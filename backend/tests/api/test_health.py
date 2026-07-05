"""
API 基础测试 — 健康检查
"""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """测试健康检查端点"""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ZhiYi API"
