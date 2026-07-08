"""
LLM 客户端封装 — 统一的 AI 模型调用接口
"""

from typing import AsyncIterator

import httpx
from loguru import logger

from app.core.config import settings


class LLMClient:
    """通用 LLM 客户端，支持 OpenAI 兼容 API"""

    def __init__(self):
        self.base_url = settings.LLM_API_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """非流式对话 — 返回完整回复"""
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """流式对话 — 逐块 yield 文本增量"""
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as resp:
                if resp.status_code >= 400:
                    error_body = ""
                    async for chunk in resp.aiter_text():
                        error_body += chunk
                        if len(error_body) > 500:
                            break
                    logger.error(f"LLM API 返回错误 HTTP {resp.status_code}: {error_body[:300]}")
                    raise RuntimeError(f"AI 服务返回错误 (HTTP {resp.status_code})。请检查 LLM_API_KEY 是否正确且未过期。")
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk == "[DONE]":
                            break
                        try:
                            import json

                            data = json.loads(chunk)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue

    async def chat_with_retry(self, messages: list[dict], retries: int = 3) -> str:
        """带重试的非流式对话"""
        for attempt in range(retries):
            try:
                return await self.chat(messages)
            except Exception as e:
                logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{retries}): {e}")
                if attempt == retries - 1:
                    raise
        raise RuntimeError("LLM 调用失败，已达最大重试次数")


# 全局单例
llm_client = LLMClient()
