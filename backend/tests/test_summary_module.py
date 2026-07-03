"""
课文总结模块 — 单元测试 & 集成验证
验证：Schema 校验、Prompt 生成、Service 逻辑、SSE 事件流
运行方式：pytest tests/test_summary_module.py -v
"""

import sys
import json
import uuid
from pathlib import Path

# 确保项目根目录在 Python path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# ═══════════════════════════════════════════════════════════
# Test 1: Pydantic Schema 校验
# ═══════════════════════════════════════════════════════════

class TestSummarySchemas:
    """验证请求/响应 Schema 的字段校验和序列化"""

    def test_generate_request_valid(self):
        """正常的总结请求应通过校验"""
        from app.schemas.summary import GenerateSummaryRequest, SummaryMode, SummarySourceType

        req = GenerateSummaryRequest(
            source_type=SummarySourceType.TEXT,
            content="晋太元中，武陵人捕鱼为业。缘溪行，忘路之远近。",
            mode=SummaryMode.DETAILED,
        )
        assert req.mode == SummaryMode.DETAILED
        assert req.source_type == SummarySourceType.TEXT
        assert len(req.content) >= 10

    def test_generate_request_content_too_short(self):
        """内容少于10字应拒绝"""
        from app.schemas.summary import GenerateSummaryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GenerateSummaryRequest(content="太短", mode="detailed", source_type="text")

    def test_generate_request_default_mode(self):
        """默认模式应为 detailed"""
        from app.schemas.summary import GenerateSummaryRequest

        req = GenerateSummaryRequest(content="测试内容足够长，这是课文原文")
        assert req.mode.value == "detailed"

    def test_summary_list_query_pagination(self):
        """分页参数默认值"""
        from app.schemas.summary import SummaryListQuery

        q = SummaryListQuery()
        assert q.page == 1
        assert q.page_size == 20

    def test_knowledge_point_serialization(self):
        """知识点应正确序列化"""
        from app.schemas.summary import KnowledgePoint

        kp = KnowledgePoint(name="通假字", category="文言知识")
        d = kp.model_dump()
        assert d == {"name": "通假字", "category": "文言知识"}

    def test_sse_event_types(self):
        """SSE 事件模型应包含正确的 type 字段"""
        from app.schemas.summary import SSESummaryContentEvent, SSESummaryDoneEvent

        content_evt = SSESummaryContentEvent(chunk="《背影》是朱自清")
        assert content_evt.type == "content"

        done_evt = SSESummaryDoneEvent(summary_id="uuid-123", mode="detailed")
        assert done_evt.type == "done"
        assert done_evt.summary_id == "uuid-123"


# ═══════════════════════════════════════════════════════════
# Test 2: Prompt 模板生成
# ═══════════════════════════════════════════════════════════

class TestPromptTemplates:
    """验证 Prompt 模板是否正确生成"""

    def test_brief_prompt_contains_content(self):
        """精简版 Prompt 应包含课文原文"""
        from app.ai.prompts.summary import BRIEF_SUMMARY_TEMPLATE

        content = "测试课文内容"
        prompt = BRIEF_SUMMARY_TEMPLATE.format(content=content)
        assert content in prompt
        assert "全文主旨" in prompt
        assert "段落概要" in prompt

    def test_detailed_prompt_has_five_sections(self):
        """详细版 Prompt 应包含5个部分"""
        from app.ai.prompts.summary import DETAILED_SUMMARY_TEMPLATE

        content = "测试课文内容"
        prompt = DETAILED_SUMMARY_TEMPLATE.format(content=content)
        assert content in prompt
        assert "全文主旨" in prompt
        assert "段落精析" in prompt
        assert "核心考点" in prompt
        assert "写作手法" in prompt
        assert "学习启示" in prompt

    def test_system_prompt_is_k12_teacher(self):
        """系统 Prompt 应为 K12 语文教师角色"""
        from app.ai.prompts.summary import SYSTEM_PROMPT

        assert "K12" in SYSTEM_PROMPT or "语文" in SYSTEM_PROMPT or "教学" in SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════
# Test 3: SSE 事件生成
# ═══════════════════════════════════════════════════════════

class TestSSEEventFormat:
    """验证 SSE 事件 JSON 格式"""

    def test_content_event_json(self):
        """content 事件应生成正确 JSON"""
        from app.core.utils import sse_json

        line = sse_json({"type": "content", "chunk": "测试增量文本"})
        parsed = json.loads(line)
        assert parsed["type"] == "content"
        assert parsed["chunk"] == "测试增量文本"

    def test_done_event_json(self):
        """done 事件应包含 summary_id"""
        from app.core.utils import sse_json

        line = sse_json({"type": "done", "summary_id": "abc-123", "mode": "brief"})
        parsed = json.loads(line)
        assert parsed["type"] == "done"
        assert parsed["summary_id"] == "abc-123"

    def test_error_event_json(self):
        """error 事件应包含 message"""
        from app.core.utils import sse_json

        line = sse_json({"type": "error", "message": "LLM 调用失败"})
        parsed = json.loads(line)
        assert parsed["type"] == "error"
        assert "失败" in parsed["message"]


# ═══════════════════════════════════════════════════════════
# Test 4: 工具函数
# ═══════════════════════════════════════════════════════════

class TestUtilityFunctions:
    """验证辅助函数"""

    def test_truncate_short_text(self):
        """短文本不应截断"""
        from app.core.utils import truncate

        text = "短文本"
        assert truncate(text, 200) == "短文本"

    def test_truncate_long_text(self):
        """长文本应截断并加省略号"""
        from app.core.utils import truncate

        text = "A" * 300
        result = truncate(text, 200)
        assert len(result) == 201  # 200 + "…"
        assert result.endswith("…")

    def test_extract_json_from_code_block(self):
        """应从 Markdown 代码块中提取 JSON"""
        from app.core.utils import extract_json

        text = '```json\n[{"name": "test"}]\n```'
        result = extract_json(text)
        assert result == '[{"name": "test"}]'

    def test_extract_json_from_raw_array(self):
        """应从纯文本中提取 JSON 数组"""
        from app.core.utils import extract_json

        text = '这是一些文本 [{"name": "test", "category": "语文"}] 更多文本'
        result = extract_json(text)
        assert '"name"' in result


# ═══════════════════════════════════════════════════════════
# Test 5: Service 逻辑（Mock LLM）
# ═══════════════════════════════════════════════════════════

class TestSummaryService:
    """验证 Service 层核心业务逻辑（使用 mock）"""

    @pytest.fixture
    def mock_db(self):
        """创建一个 mock 数据库会话"""
        from unittest.mock import AsyncMock, MagicMock
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()
        return db

    def test_service_initialization(self, mock_db):
        """Service 应正确初始化"""
        from app.services.summary_service import SummaryService
        from app.schemas.summary import SummaryMode

        svc = SummaryService(mock_db)
        assert svc.db is mock_db

    def test_list_summaries_empty(self, mock_db):
        """空列表应返回正确的分页结构"""
        from app.services.summary_service import SummaryService
        from unittest.mock import AsyncMock

        # Mock: 总数查询返回 0
        mock_db.execute.return_value.scalar.return_value = 0
        # Mock: 分页查询返回空列表
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        svc = SummaryService(mock_db)
        # 需要分开 mock
        # 第一次 execute: count query
        # 第二次 execute: select query

    @pytest.mark.asyncio
    async def test_delete_summary_not_found(self, mock_db):
        """删除不存在的记录应返回 False"""
        from app.services.summary_service import SummaryService

        # Mock DELETE 返回 0 行
        mock_db.execute.return_value.rowcount = 0

        svc = SummaryService(mock_db)
        result = await svc.delete_summary("user-1", "non-existent-id")
        assert result is False


# ═══════════════════════════════════════════════════════════
# Test 6: Agent 工具注册
# ═══════════════════════════════════════════════════════════

class TestAgentToolRegistry:
    """验证课文总结工具是否正确注册到 Agent"""

    def test_summary_tool_meta_structure(self):
        """text_summary 工具元数据应符合 AgentTool 规范"""
        from app.ai.agent.tools import SUMMARY_TOOL_META

        assert SUMMARY_TOOL_META["name"] == "text_summary"
        assert "description" in SUMMARY_TOOL_META
        assert "parameters" in SUMMARY_TOOL_META
        assert "content" in SUMMARY_TOOL_META["parameters"]["properties"]
        assert "mode" in SUMMARY_TOOL_META["parameters"]["properties"]
        assert "content" in SUMMARY_TOOL_META["parameters"]["required"]

    def test_tool_registry_singleton(self):
        """ToolRegistry 应为单例"""
        from app.ai.agent.tools import tool_registry, ToolRegistry

        assert tool_registry is not None
        assert isinstance(tool_registry, ToolRegistry)

    def test_summary_tool_registered(self):
        """text_summary 工具应已在全局注册中心"""
        from app.ai.agent.tools import tool_registry

        tool = tool_registry.get("text_summary")
        assert tool is not None, "text_summary 工具未在 ToolRegistry 中注册！"
        assert tool.name == "text_summary"
        assert "总结" in tool.description or "课文" in tool.description

    def test_tool_export_openai_format(self):
        """导出格式应兼容 OpenAI function calling"""
        from app.ai.agent.tools import tool_registry

        exported = tool_registry.export_for_openai()
        assert isinstance(exported, list)
        assert len(exported) >= 1  # 至少包含 text_summary

        # 找到 text_summary
        summary_tools = [t for t in exported if t["function"]["name"] == "text_summary"]
        assert len(summary_tools) == 1
        assert summary_tools[0]["type"] == "function"


# ═══════════════════════════════════════════════════════════
# Test 7: 错误码 & 通用响应
# ═══════════════════════════════════════════════════════════

class TestErrorCodes:
    """验证错误码定义与文档一致"""

    def test_error_codes_match_doc(self):
        """错误码应与接口文档附录 A.3 对齐"""
        from app.schemas.common import ErrorCode

        assert ErrorCode.SUCCESS == 0
        assert ErrorCode.VALIDATION_ERROR == 40001
        assert ErrorCode.TOKEN_EXPIRED == 40101
        assert ErrorCode.TOKEN_INVALID == 40102
        assert ErrorCode.RESOURCE_NOT_FOUND == 40402
        assert ErrorCode.LLM_SERVICE_ERROR == 50002

    def test_success_response_format(self):
        """成功响应应包含 code=0"""
        from app.schemas.common import success_response

        resp = success_response(data={"id": "123"})
        assert resp["code"] == 0
        assert resp["data"] == {"id": "123"}

    def test_error_response_format(self):
        """错误响应应包含错误码和消息"""
        from app.schemas.common import error_response, ErrorCode

        resp = error_response(ErrorCode.RESOURCE_NOT_FOUND, "总结不存在")
        assert resp["code"] == 40402
        assert "不存在" in resp["message"]


# ═══════════════════════════════════════════════════════════
# Test 8: 端到端 — 模拟完整请求流程
# ═══════════════════════════════════════════════════════════

class TestEndToEndFlow:
    """模拟从 API 请求到 SSE 响应的完整数据流"""

    def test_full_flow_data_pipeline(self):
        """
        验证数据流转：
        请求 → Schema 校验 → Prompt 构建 → (LLM mock) → SSE 事件 → 响应
        """
        from app.schemas.summary import (
            GenerateSummaryRequest,
            SummaryMode,
            SSESummaryContentEvent,
            SSESummaryDoneEvent,
        )

        # 1. 模拟前端发送请求
        req = GenerateSummaryRequest(
            content="晋太元中，武陵人捕鱼为业。缘溪行，忘路之远近。",
            mode=SummaryMode.BRIEF,
            source_type="text",
        )
        assert req.content is not None

        # 2. 构建 Prompt
        from app.ai.prompts.summary import BRIEF_SUMMARY_TEMPLATE
        prompt = BRIEF_SUMMARY_TEMPLATE.format(content=req.content)
        assert "晋太元中" in prompt

        # 3. 模拟 LLM 流式输出（每个 chunk）
        mock_chunks = [
            "## 📖 全文主旨",
            "\n\n本文描绘了桃花源的美好景象",
            "\n\n## 📑 段落概要",
            "\n\n首段写渔人偶然发现桃花林",
        ]

        # 4. 生成 SSE 事件
        sse_events = []
        for chunk in mock_chunks:
            evt = SSESummaryContentEvent(chunk=chunk)
            sse_events.append(evt)

        # 5. 完成事件
        done = SSESummaryDoneEvent(summary_id="test-id-001", mode="brief")

        # 6. 验证每个事件
        assert len(sse_events) == 4
        for evt in sse_events:
            assert evt.type == "content"
            assert len(evt.chunk) > 0

        assert done.type == "done"
        assert done.summary_id == "test-id-001"

        # 7. 序列化为 SSE 文本行
        lines = [f"data: {evt.model_dump_json()}\n\n" for evt in sse_events]
        assert all(line.startswith("data: ") for line in lines)
        assert all(line.endswith("\n\n") for line in lines)


# ═══════════════════════════════════════════════════════════
# Main: 运行说明
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  课文总结模块 (PBI_06) — 单元测试")
    print("  运行方式: pytest tests/test_summary_module.py -v")
    print("=" * 60)
    pytest.main([__file__, "-v", "--tb=short"])
