"""
Agent 任务编排器 (PBI_04, PBI_12)

负责:
1. 解析用户意图（LLM 驱动）
2. 拆解任务步骤
3. 调用 LLM + 工具链执行（Function Calling）
4. 生成思考链（PBI_12）
5. SSE 流式输出事件
"""

import json
from typing import AsyncIterator

from loguru import logger

from app.ai.agent.tools import tool_registry
from app.ai.llm_client import llm_client

SYSTEM_PROMPT = """你是智翼（ZhiYi）AI 学习助手，专为 K12 学生提供学习辅导。

## 你的能力
- **习题生成**：根据学科、知识点、难度生成各类练习题（选择/填空/简答/计算/辨析）
- **习题批改**：对学生的作答进行批改，给出评分和纠错建议
- **知识图谱**：基于知识点构建知识图谱，展示知识关联
- **文件解析**：解析上传的学习资料（PDF/DOCX/TXT等）

## 任务处理流程
1. 仔细分析用户的请求，识别所有需要完成的任务
2. 将复杂任务拆解为清晰的执行步骤
3. 按步骤执行，需要时调用对应的工具函数
4. 整合所有结果，以清晰、友好的方式呈现

## 回复要求
- 使用中文回复，语气亲切适合学生
- 回答要结构清晰，善用小标题和分点
- 对于习题类任务，题目和解析要分开呈现
- 鼓励学生思考，适当给予学习建议"""


class AgentOrchestrator:
    """Agent 编排器 — 将用户自然语言指令转为多步骤任务执行"""

    @staticmethod
    async def analyze_intent(message: str) -> list[dict]:
        """
        使用 LLM 分析用户意图，返回任务步骤列表。

        返回格式:
        [
            {
                "step": 1,
                "title": "需求分析",
                "content": "识别到习题生成任务",
                "tool_name": "exercise_generate"  # 可选，需要调用的工具名
            },
            ...
        ]
        """
        available_tools = tool_registry.list_tools()
        tool_descriptions = "\n".join(
            f"- **{t.name}**: {t.description}" for t in available_tools
        ) if available_tools else "（暂无可用工具）"

        intent_prompt = f"""分析以下用户消息，拆解为执行步骤。

用户消息："{message}"

当前可用工具：
{tool_descriptions}

请以 JSON 数组格式返回步骤列表，每个步骤包含：
- step: 步骤序号 (从 1 开始)
- title: 步骤标题 (≤10字)
- content: 步骤描述
- tool_name: 如果需要调用工具，填写工具名称；否则为 null

如果用户只是闲聊或咨询，返回一个通用问答步骤。
只返回 JSON 数组，不要包含其他文字。"""

        try:
            response = await llm_client.chat(
                messages=[{"role": "user", "content": intent_prompt}],
                temperature=0.3,
                max_tokens=1024,
            )
            # 尝试提取 JSON
            response = response.strip()
            if response.startswith("```"):
                # 去掉 markdown 代码块标记
                lines = response.split("\n")
                response = "\n".join(lines[1:-1])
            steps = json.loads(response)
            if isinstance(steps, list) and len(steps) > 0:
                return steps
        except Exception as e:
            logger.warning(f"[Agent] LLM 意图分析失败，回退到关键词匹配: {e}")

        # 回退：简单关键词匹配
        return AgentOrchestrator._fallback_intent(message)

    @staticmethod
    def _fallback_intent(message: str) -> list[dict]:
        """关键词匹配的意图分析（LLM 不可用时的回退方案）"""
        steps = []
        step_num = 1

        if any(kw in message for kw in ["出题", "习题", "题目", "练习", "做题", "试卷"]):
            steps.append({
                "step": step_num, "title": "习题生成",
                "content": "识别到习题生成需求，根据知识点生成练习题",
                "tool_name": "exercise_generate",
            })
            step_num += 1

        if any(kw in message for kw in ["批改", "对答案", "批阅", "改错", "打分"]):
            steps.append({
                "step": step_num, "title": "批改反馈",
                "content": "识别到批改需求，对作答进行评分与纠错",
                "tool_name": "exercise_grade",
            })
            step_num += 1

        if any(kw in message for kw in ["知识图谱", "知识点", "思维导图", "知识网络"]):
            steps.append({
                "step": step_num, "title": "知识图谱",
                "content": "识别到知识图谱需求，构建知识点关联网络",
                "tool_name": "knowledge_graph",
            })
            step_num += 1

        if not steps:
            steps.append({
                "step": 1, "title": "智能问答",
                "content": "理解用户问题，提供学习辅导",
                "tool_name": None,
            })

        return steps

    async def run_stream(
        self,
        user_message: str,
        history: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """
        流式执行 Agent 任务，通过 SSE yield 事件。

        SSE 事件类型:
        - {"type": "thought", "step": N, "title": "...", "content": "..."}
        - {"type": "content", "chunk": "..."}
        - {"type": "tool_start", "tool_name": "...", "step": N}
        - {"type": "tool_result", "tool_name": "...", "result": "..."}
        - {"type": "done", "session_id": "...", "usage": {...}}
        - {"type": "error", "message": "..."}

        参数:
            user_message: 用户输入
            history: 历史消息列表 [{"role":"user/assistant","content":"..."}]
        """
        thought_chain: list[dict] = []
        tool_calls_record: list[dict] = []

        # ================================================================
        # Phase 1: 意图分析 → 思考链
        # ================================================================
        yield {
            "type": "thought",
            "step": 0,
            "title": "分析中",
            "content": "正在理解你的需求...",
        }

        intent_steps = await self.analyze_intent(user_message)
        for step in intent_steps:
            thought_item = {
                "step": step["step"],
                "title": step["title"],
                "content": step["content"],
            }
            thought_chain.append(thought_item)
            yield {
                "type": "thought",
                "step": step["step"],
                "title": step["title"],
                "content": step["content"],
            }
            logger.info(f"[Agent] 意图分析 | step={step['step']} | {step['title']}")

        # ================================================================
        # Phase 2: 执行工具调用（如有需要）
        # ================================================================
        tool_results_context = ""
        for step in intent_steps:
            tool_name = step.get("tool_name")
            if not tool_name:
                continue

            tool = tool_registry.get(tool_name)
            if not tool:
                logger.warning(f"[Agent] 工具未注册: {tool_name}")
                continue

            yield {
                "type": "tool_start",
                "tool_name": tool_name,
                "step": step["step"],
            }
            logger.info(f"[Agent] 调用工具 | tool={tool_name}")

            try:
                # 从用户消息中提取工具所需参数
                tool_params = await self._extract_tool_params(
                    tool_name, user_message, tool.parameters
                )
                result = await tool.handler(**tool_params)
                result_str = (
                    result if isinstance(result, str)
                    else json.dumps(result, ensure_ascii=False)
                )

                tool_calls_record.append({
                    "tool_name": tool_name,
                    "step": step["step"],
                    "params": tool_params,
                    "result": result_str[:500],  # 截断存储
                })

                yield {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "result": result_str,
                }

                tool_results_context += f"\n\n【工具调用结果：{tool_name}】\n{result_str[:2000]}"

            except Exception as e:
                logger.error(f"[Agent] 工具执行失败 | tool={tool_name} | error={e}")
                yield {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "result": f"工具执行失败: {str(e)}",
                }

        # ================================================================
        # Phase 3: LLM 流式生成最终回复
        # ================================================================
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # 如果有工具执行结果，追加到上下文
        if tool_results_context:
            messages.append({
                "role": "system",
                "content": f"以下是你调用工具获得的结果，请基于这些结果回答用户：{tool_results_context}",
            })

        try:
            full_response = ""
            async for chunk in llm_client.chat_stream(messages):
                full_response += chunk
                yield {"type": "content", "chunk": chunk}

            # 完成事件
            yield {
                "type": "done",
                "session_id": session_id,
                "usage": {"tokens": len(full_response)},
            }

        except Exception as e:
            logger.error(f"[Agent] LLM 流式调用失败 | error={e}")
            yield {
                "type": "error",
                "message": f"AI 服务暂时不可用，请稍后重试: {str(e)}",
            }

    async def _extract_tool_params(
        self, tool_name: str, user_message: str, parameters_schema: dict
    ) -> dict:
        """
        使用 LLM 从用户消息中提取工具调用参数。

        参数:
            tool_name: 工具名称
            user_message: 用户原始消息
            parameters_schema: 工具的 JSON Schema 参数定义
        """
        required_params = parameters_schema.get("required", [])
        properties = parameters_schema.get("properties", {})

        # 构建参数提取提示
        param_descriptions = []
        for name, prop in properties.items():
            desc = prop.get("description", "")
            param_type = prop.get("type", "string")
            required = "必填" if name in required_params else "可选"
            param_descriptions.append(f"  - {name} ({param_type}, {required}): {desc}")

        extract_prompt = f"""从用户消息中提取工具 "{tool_name}" 所需的参数。

参数说明：
{chr(10).join(param_descriptions)}

用户消息："{user_message}"

请以 JSON 对象格式返回参数值，只返回 JSON，不要包含其他文字。
对于可选参数，如果用户没有提供则不要包含该字段。"""

        try:
            response = await llm_client.chat(
                messages=[{"role": "user", "content": extract_prompt}],
                temperature=0.1,
                max_tokens=512,
            )
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:-1])
            params = json.loads(response)
            return params
        except Exception as e:
            logger.warning(f"[Agent] 参数提取失败，使用默认值: {e}")
            # 回退：提供空参数（工具应该能处理）
            return {"content": user_message}


# 全局编排器单例
agent_orchestrator = AgentOrchestrator()
