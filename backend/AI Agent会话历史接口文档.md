# AI Agent 会话历史 — 接口说明文档

> Base URL: `http://localhost:8000/api/v1`  
> 认证方式: `Authorization: Bearer <access_token>`  
> 所有响应遵循统一格式: `{"code": 0, "message": "ok", "data": ...}`

---

## 1. 会话列表（按日期分组）

用于侧边栏历史记录列表，仿 DeepSeek 网页版按日期分组。

```
GET /agent/sessions
```

**请求参数**: 无

**响应示例**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "groups": [
      {
        "label": "今天",
        "sessions": [
          {
            "id": "a1b2c3d4-...",
            "title": "帮我总结《桃花源记》的主要内容",
            "created_at": "2026-07-07T14:30:00Z",
            "updated_at": "2026-07-07T15:20:00Z"
          }
        ]
      },
      {
        "label": "昨天",
        "sessions": [
          {
            "id": "e5f6g7h8-...",
            "title": "二次函数怎么求解",
            "created_at": "2026-07-06T09:15:00Z",
            "updated_at": "2026-07-06T10:00:00Z"
          }
        ]
      },
      {
        "label": "本周",
        "sessions": [...]
      },
      {
        "label": "更早",
        "sessions": [...]
      }
    ]
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `groups` | array | 按日期分组，仅返回非空分组 |
| `groups[].label` | string | 分组标签：`今天` / `昨天` / `本周` / `更早` |
| `groups[].sessions` | array | 该分组下的会话列表，按 `updated_at` 倒序 |
| `sessions[].id` | string (UUID) | 会话唯一标识 |
| `sessions[].title` | string | 会话标题（自动生成或用户自定义） |
| `sessions[].created_at` | datetime | 创建时间 |
| `sessions[].updated_at` | datetime | 最后更新时间 |

---

## 2. 会话详情（历史消息）

点击某个会话时加载全部历史消息。

```
GET /agent/sessions/{session_id}
```

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | string (UUID) | 会话 ID |

**响应示例**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "a1b2c3d4-...",
    "title": "帮我总结《桃花源记》的主要内容",
    "created_at": "2026-07-07T14:30:00Z",
    "updated_at": "2026-07-07T15:20:00Z",
    "messages": [
      {
        "id": 1,
        "session_id": "a1b2c3d4-...",
        "role": "user",
        "content": "帮我总结《桃花源记》的主要内容",
        "thought_chain": null,
        "tool_calls": null,
        "created_at": "2026-07-07T14:30:00Z"
      },
      {
        "id": 2,
        "session_id": "a1b2c3d4-...",
        "role": "assistant",
        "content": "《桃花源记》是东晋诗人陶渊明的代表作之一...",
        "thought_chain": [
          {
            "step": 1,
            "title": "课文总结",
            "description": "识别到课文总结需求"
          }
        ],
        "tool_calls": null,
        "created_at": "2026-07-07T14:30:15Z"
      }
    ]
  }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `messages` | array | 消息列表，按时间正序排列 |
| `messages[].role` | string | `user` 或 `assistant` |
| `messages[].content` | string | 消息正文 |
| `messages[].thought_chain` | array \| null | 思考链步骤（仅 AI 回复时有值） |
| `messages[].tool_calls` | array \| null | 工具调用记录 |

---

## 3. 修改会话标题

用户右键/双击标题时触发的重命名。

```
PATCH /agent/sessions/{session_id}/title
```

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | string (UUID) | 会话 ID |

**请求体**:
```json
{
  "title": "桃花源记课文总结"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `title` | string | 是 | 新标题，1-100 字符 |

**响应示例**:
```json
{
  "code": 0,
  "message": "标题已更新",
  "data": {
    "id": "a1b2c3d4-...",
    "title": "桃花源记课文总结"
  }
}
```

---

## 4. 删除会话

删除整个会话及其下的所有消息（级联删除）。

```
DELETE /agent/sessions/{session_id}
```

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `session_id` | string (UUID) | 会话 ID |

**响应示例**:
```json
{
  "code": 0,
  "message": "会话已删除",
  "data": null
}
```

---

## 5. 发送对话消息 [SSE]

创建新会话或继续已有会话，返回 Server-Sent Events 流式响应。

```
POST /agent/chat
```

**请求体**:
```json
{
  "session_id": null,
  "message": "帮我总结《背影》这篇课文"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `session_id` | string \| null | 是 | 传 `null` 创建新会话；传已有 ID 继续对话 |
| `message` | string | 是 | 用户输入，最少 1 字符 |

**SSE 事件流格式** (`Content-Type: text/event-stream`):

```
data: {"type":"thought","step":1,"title":"课文总结","content":"识别到课文总结需求"}

data: {"type":"content","chunk":"《背影》是朱自清"}

data: {"type":"content","chunk":"的散文名篇..."}

data: {"type":"done","session_id":"a1b2c3d4-...","usage":{"total_chars":1234}}
```

**SSE 事件类型**:

| type | 说明 | 前端处理 |
|------|------|------|
| `thought` | 思考链步骤（PBI_12） | 渲染到思考链面板 |
| `content` | 文本增量 | 追加到对话区，打字机效果 |
| `done` | 对话完成 | 保存 `session_id`，切换到结果态 |
| `error` | 异常 | 显示错误提示 |

**`done` 事件额外字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 当前会话 ID，前端需保存用于后续请求 |
| `usage` | object | 用量统计 |

---

## 错误码

| code | HTTP | 说明 |
|------|------|------|
| 40101 | 401 | Token 过期 |
| 40102 | 401 | Token 无效 |
| 40402 | 404 | 会话不存在或无权访问 |

---

## 前端对接要点

### 1. 侧边栏历史列表

```
初始化时调用 GET /agent/sessions
→ 按 groups 渲染"今天/昨天/本周/更早"分组
→ 每个 session 显示 title（超出长度用 CSS text-overflow: ellipsis）
→ 点击某个 session → 调用 GET /agent/sessions/{id} 加载消息
```

### 2. 新建对话

```
用户点击"新建对话"按钮
→ 清空当前对话区
→ session_id = null
→ 等待用户输入第一条消息
→ 调用 POST /agent/chat { session_id: null, message: "..." }
→ 从 SSE done 事件中获取新 session_id 并保存
→ 对话结束后自动生成标题（服务端完成），前端无需额外调用
```

### 3. 重命名

```
用户双击标题 / 点击编辑图标
→ 显示输入框，预填当前标题
→ 确认后调用 PATCH /agent/sessions/{id}/title
→ 成功后更新本地列表中的 title
```

### 4. 删除

```
用户点击删除按钮
→ 弹确认框
→ 调用 DELETE /agent/sessions/{id}
→ 成功后从本地列表移除
→ 如果当前正在查看该会话，切换到空白对话页
```

### 5. SSE 流式接收

```typescript
// 使用 fetch + ReadableStream（不支持 EventSource，因为需要 POST）
const response = await fetch('/api/v1/agent/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    'Accept': 'text/event-stream',
  },
  body: JSON.stringify({ session_id: null, message: '...' }),
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const text = decoder.decode(value);
  for (const line of text.split('\n')) {
    if (line.startsWith('data: ')) {
      const event = JSON.parse(line.slice(6));
      // 按 event.type 分发处理
    }
  }
}
```
