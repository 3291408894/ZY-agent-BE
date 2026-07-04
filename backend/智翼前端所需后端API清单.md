# 智翼前端所需后端 API 清单

> **用途**：指导 FastAPI 后端开发者生成对应接口  
> **对应前端**：`D:\VScode\zy-fe\frontend\`  
> **生成日期**：2026-07-04  
> **总计**：31 个端点（3 个 SSE 流式 + 28 个 REST）

---

## 一、通用约定

### 1.1 基础信息

| 项目 | 值 |
|------|-----|
| Base URL | `/api/v1` |
| 认证方式 | JWT Bearer Token（Header: `Authorization: Bearer <token>`） |
| Content-Type | `application/json`（文件上传除外） |
| 分页参数 | `?page=1&page_size=20`（page_size 最大 100） |

### 1.2 统一响应格式

```json
// 成功
{ "code": 0, "message": "ok", "data": { ... } }

// 分页成功
{ "code": 0, "message": "ok", "data": { "items": [...], "total": 128, "page": 1, "page_size": 20, "total_pages": 7 } }

// 错误
{ "code": 40001, "message": "邮箱已被注册", "detail": null }
```

### 1.3 [SSE] 流式端点约定

标注 `[SSE]` 的接口使用 Server-Sent Events，`Content-Type: text/event-stream`。

**标准 SSE 事件格式**：
```
data: {"type":"<event_type>","...字段"}
```

**事件类型语义**：
| type | 含义 | 前端行为 |
|------|------|---------|
| `thought` | 思考步骤（PBI_12） | 渲染到思考链面板 |
| `content` | 文本增量块 | 追加到对话区（打字机效果） |
| `done` | 流式结束 | 保存结果、更新 UI |
| `error` | 错误 | 显示错误、停止流式 |
| `progress` | 进度（习题生成用） | 更新进度条 |
| `exercise` | 单道习题（习题生成用） | 逐题追加渲染 |

---

## 二、认证模块（PBI_01）

### 2.1 注册

```
POST /api/v1/auth/register
认证：否
```

**Request:**
```json
{
  "email": "student@example.com",
  "phone": "13800138000",
  "password": "Abc123456!",
  "grade": "七年级",
  "subjects": ["语文", "数学", "英语"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 否* | 邮箱（email 和 phone 至少一个） |
| phone | string | 否* | 手机号 |
| password | string | 是 | 8-64 位 |
| grade | string | 是 | 年级，如"七年级" |
| subjects | string[] | 是 | 学科偏好，至少 1 个 |

**Response (201):**
```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "user_id": "uuid",
    "email": "student@example.com",
    "grade": "七年级"
  }
}
```

---

### 2.2 登录

```
POST /api/v1/auth/login
认证：否
```

**Request:**
```json
{
  "login": "student@example.com",
  "password": "Abc123456!"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| login | string | 是 | 邮箱或手机号 |
| password | string | 是 | 密码 |

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "access_token": "eyJhbGci...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "id": "uuid",
      "email": "student@example.com",
      "phone": null,
      "nickname": "小明",
      "grade": "七年级",
      "subjects": ["语文", "数学", "英语"],
      "textbook_version": null,
      "avatar_url": null
    }
  }
}
```

**注意**：`user` 对象中不需要返回 `created_at` / `updated_at`——前端登录后的 Store 只存轻量 `IUserBrief`。

---

### 2.3 发送重置密码验证码

```
POST /api/v1/auth/reset-password
认证：否
```

**Request:**
```json
{
  "email": "student@example.com"
}
```

**Response (200):**
```json
{ "code": 0, "message": "验证码已发送", "data": null }
```

**逻辑**：生成 6 位验证码，发送到邮箱，存入 Redis（TTL 300s）。

---

### 2.4 验证并重置密码

```
POST /api/v1/auth/reset-password/verify
认证：否
```

**Request:**
```json
{
  "email": "student@example.com",
  "code": "123456",
  "new_password": "NewPass123!"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | |
| code | string | 是 | 6 位验证码 |
| new_password | string | 是 | 新密码，8-64 位 |

**Response (200):**
```json
{ "code": 0, "message": "密码重置成功", "data": null }
```

---

### 2.5 获取个人资料

```
GET /api/v1/users/profile
认证：是
```

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "uuid",
    "email": "student@example.com",
    "phone": null,
    "nickname": "小明",
    "grade": "七年级",
    "subjects": ["语文", "数学"],
    "textbook_version": "部编版",
    "avatar_url": null,
    "created_at": "2026-07-03T10:00:00Z",
    "updated_at": "2026-07-03T10:00:00Z"
  }
}
```

**注意**：与登录返回不同，这里需要 `created_at` 和 `updated_at`。

---

### 2.6 更新个人资料

```
PUT /api/v1/users/profile
认证：是
```

**Request:**
```json
{
  "nickname": "小华",
  "grade": "八年级",
  "subjects": ["语文", "数学", "物理"],
  "textbook_version": "人教版"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nickname | string | 否 | |
| grade | string | 否 | |
| subjects | string[] | 否 | |
| textbook_version | string | 否 | |

**Response (200):** 返回更新后的完整 `IUserProfile`（同 §2.5 响应）。

---

### 2.7 学习仪表盘

```
GET /api/v1/users/dashboard
认证：是
```

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total_study_time": 36000,
    "total_exercises": 128,
    "correct_rate": 0.85,
    "recent_summaries": [ ... ],
    "recent_exercises": [ ... ],
    "recommendations": [ ... ],
    "weak_points": ["文言文阅读", "二次函数"]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| total_study_time | number | 累计学习时长（秒） |
| total_exercises | number | 累计做题数 |
| correct_rate | number | 正确率 0-1 |
| recent_summaries | ISummaryItem[] | 最近总结（最多 5 条） |
| recent_exercises | any[] | 最近习题 |
| recommendations | any[] | 推荐内容 |
| weak_points | string[] | 薄弱知识点 |

---

## 三、AI Agent 模块（PBI_04, PBI_12）

### 3.1 创建对话 [SSE]

```
POST /api/v1/agent/chat
Content-Type: application/json
Accept: text/event-stream
认证：是
```

**Request:**
```json
{
  "session_id": null,
  "message": "帮我总结《背影》这篇课文的主要内容，然后出几道阅读理解题"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string\|null | 否 | null 时后端自动创建新会话 |
| message | string | 是 | 用户输入 |

**SSE 事件流：**
```
data: {"type":"thought","step":1,"title":"需求分析","content":"识别到两个任务：1.课文总结 2.阅读理解题生成"}

data: {"type":"thought","step":2,"title":"调用工具","content":"正在调用【课文总结】工具..."}

data: {"type":"content","chunk":"《背影》是朱自清"}

data: {"type":"content","chunk":"的散文名篇，主要讲述了..."}

data: {"type":"tool_call","tool_name":"text_summary","parameters":{...},"result":"总结文本"}

data: {"type":"done","session_id":"uuid-xxx","usage":{"tokens":1234}}
```

**每个 SSE 事件的具体字段：**

**thought 事件：**
```json
{ "type": "thought", "step": 1, "title": "需求分析", "content": "识别到..." }
```

**content 事件：**
```json
{ "type": "content", "chunk": "文本片段" }
```

**tool_call 事件：**
```json
{ "type": "tool_call", "tool_name": "text_summary", "parameters": {...}, "result": "工具返回摘要" }
```

**done 事件：**
```json
{ "type": "done", "session_id": "uuid-xxx", "usage": {"tokens": 1234} }
```

**error 事件：**
```json
{ "type": "error", "message": "LLM 服务不可用" }
```

**后端逻辑**：
1. 若 `session_id` 为 null → 创建新会话（`chat_sessions` 表新增一行，title 用用户第一条消息截取）
2. 保存用户消息到 `chat_messages`
3. 调用 LLM → 流式返回 thought / content / tool_call 事件
4. 完成后保存 assistant 消息（含 thought_chain + tool_calls JSON）到 `chat_messages`
5. 发送 `done` 事件（必须包含 `session_id`，前端依赖它来关联）

---

### 3.2 会话列表

```
GET /api/v1/agent/sessions
认证：是
```

**Query:** `?page=1&page_size=20`

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      { "id": "uuid", "title": "课文总结讨论", "created_at": "2026-07-03T10:00:00Z", "updated_at": "2026-07-03T10:05:00Z" }
    ],
    "total": 10,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
}
```

**注意**：`items` 中每个会话必须包含 `id`, `title`, `created_at`, `updated_at`。

---

### 3.3 获取历史消息

```
GET /api/v1/agent/sessions/{session_id}
认证：是
```

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "msg-uuid-1",
      "session_id": "uuid",
      "role": "user",
      "content": "帮我总结《背影》",
      "thought_chain": null,
      "tool_calls": null,
      "created_at": "2026-07-03T10:00:00Z"
    },
    {
      "id": "msg-uuid-2",
      "session_id": "uuid",
      "role": "assistant",
      "content": "《背影》是朱自清...",
      "thought_chain": [
        { "step": 1, "title": "需求分析", "content": "识别..." }
      ],
      "tool_calls": [
        { "tool_name": "text_summary", "parameters": {...}, "result": "...", "result_summary": "总结完成" }
      ],
      "created_at": "2026-07-03T10:00:05Z"
    }
  ]
}
```

**注意**：返回的是数组（不是分页对象）。`thought_chain` 和 `tool_calls` 存储为 JSON 字段。

---

### 3.4 删除会话

```
DELETE /api/v1/agent/sessions/{session_id}
认证：是
```

**Response (200):**
```json
{ "code": 0, "message": "删除成功", "data": null }
```

**逻辑**：级联删除关联的 `chat_messages`。

---

## 四、课文总结模块（PBI_06）

### 4.1 生成总结 [SSE]

```
POST /api/v1/summaries/generate
Content-Type: application/json
Accept: text/event-stream
认证：是
```

**Request:**
```json
{
  "source_type": "text",
  "content": "晋太元中，武陵人捕鱼为业...",
  "mode": "detailed",
  "file_id": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_type | string | 是 | `"text"` 或 `"file"` |
| content | string | 是 | 课文原文（source_type=text 时） |
| mode | string | 是 | `"brief"` 精简版 或 `"detailed"` 详细版 |
| file_id | string\|null | 否 | source_type=file 时传入文件 ID |

**SSE 事件流：**
```
data: {"type":"content","chunk":"## 全文主旨\n\n"}

data: {"type":"content","chunk":"本文描绘了..."}

data: {"type":"knowledge_points","points":[{"name":"文言实词","category":"文言知识"},{"name":"桃花源意象","category":"文学意象"}]}

data: {"type":"done","summary_id":"uuid","mode":"detailed"}
```

**knowledge_points 事件结构：**
```json
{ "type": "knowledge_points", "points": [{"name": "知识点名称", "category": "分类"}] }
```

**done 事件：**
```json
{ "type": "done", "summary_id": "uuid", "mode": "detailed" }
```

---

### 4.2 总结历史列表

```
GET /api/v1/summaries?page=1&page_size=20&mode=detailed
认证：是
```

**Query:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 默认 1 |
| page_size | int | 否 | 默认 20 |
| mode | string | 否 | `"brief"` 或 `"detailed"` 筛选 |

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "uuid",
        "source_type": "text",
        "source_content": "晋太元中...",
        "summary_text": "本文描绘了...",
        "mode": "detailed",
        "knowledge_points": [{"name": "文言实词", "category": "文言知识"}],
        "created_at": "2026-07-03T10:00:00Z"
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
}
```

**注意**：列表中的 `source_content` 和 `summary_text` 可以做截断（取前 200 字），完整内容在详情接口返回。

---

### 4.3 总结详情

```
GET /api/v1/summaries/{id}
认证：是
```

**Response (200):** 返回完整 `ISummaryDetail`，字段同 §4.2 的 item，但 `source_content` 和 `summary_text` 不截断。

---

### 4.4 删除总结

```
DELETE /api/v1/summaries/{id}
认证：是
```

**Response (200):**
```json
{ "code": 0, "message": "删除成功", "data": null }
```

---

## 五、文件管理模块（PBI_05）

### 5.1 上传文件

```
POST /api/v1/files/upload
Content-Type: multipart/form-data
认证：是
```

**Form Data:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 支持 txt / md / pdf / docx / csv / json / html / xml / yaml |
| auto_parse | bool | 否 | 是否上传后自动解析，默认 true |

**限制**：单文件 ≤ 50 MB

**Response (201):**
```json
{
  "code": 0,
  "message": "上传成功",
  "data": {
    "id": "uuid",
    "user_id": "uuid",
    "filename": "初三语文笔记.pdf",
    "file_type": "pdf",
    "file_size": 2048576,
    "storage_path": "/uploads/uuid.pdf",
    "parse_status": "processing",
    "parsed_content": null,
    "summary": null,
    "knowledge_points": null,
    "created_at": "2026-07-03T10:00:00Z"
  }
}
```

**逻辑**：上传 → 存文件 → 写入 `uploaded_files`（`parse_status: "pending"`）→ 若 `auto_parse=true` → Celery 异步解析 → 更新 `parse_status`。

---

### 5.2 文件列表

```
GET /api/v1/files?page=1&page_size=20&file_type=pdf
认证：是
```

**Query:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 默认 1 |
| page_size | int | 否 | 默认 20 |
| file_type | string | 否 | 筛选文件类型 |

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [ ... ],
    "total": 30,
    "page": 1,
    "page_size": 20,
    "total_pages": 2
  }
}
```

每个 item 结构同 §5.1 响应的 `data` 字段。

---

### 5.3 查询文件解析状态

```
GET /api/v1/files/{file_id}/status
认证：是
```

**Response (200):** 返回完整 `IUploadedFile` 对象（同 §5.1 响应 data），包含 `parsed_content`、`summary`、`knowledge_points` 最新值。

---

### 5.4 重新解析

```
POST /api/v1/files/{file_id}/reparse
认证：是
```

**Response (200):**
```json
{
  "code": 0,
  "message": "已提交重新解析",
  "data": {
    "id": "uuid",
    "parse_status": "processing",
    ...
  }
}
```

**逻辑**：重置 `parse_status="processing"` → Celery 重新解析 → 更新结果。

---

### 5.5 删除文件

```
DELETE /api/v1/files/{file_id}
认证：是
```

**Response (200):**
```json
{ "code": 0, "message": "删除成功", "data": null }
```

**逻辑**：删除文件记录 + 删除存储中的文件。

---

## 六、习题模块（PBI_08, PBI_09, PBI_10）

### 6.1 生成习题 [SSE]

```
POST /api/v1/exercises/generate
Content-Type: application/json
Accept: text/event-stream
认证：是
```

**Request:**
```json
{
  "subject": "语文",
  "grade": "七年级",
  "knowledge_points": ["桃花源记", "文言文翻译"],
  "difficulty": "medium",
  "question_types": ["choice", "fill", "short_answer"],
  "count": 5
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| subject | string | 是 | 学科 |
| grade | string | 是 | 年级 |
| knowledge_points | string[] | 是 | 知识点列表 |
| difficulty | string | 否 | `easy` / `medium` / `hard`，默认 medium |
| question_types | string[] | 是 | `choice` / `fill` / `short_answer` / `calculation` / `analysis` |
| count | int | 否 | 生成数量，1-50，默认 5 |

**SSE 事件流：**
```
data: {"type":"progress","generated":1,"total":5}

data: {"type":"exercise","exercise":{"id":"uuid-1","question":"下列加点词解释正确的是...","question_type":"choice","options":["A. 沿着","B. 因为","C. 于是","D. 跟随"],"answer":null,"analysis":null,"difficulty":"medium","knowledge_points":["文言实词"],"subject":"语文","grade":"七年级"}}

data: {"type":"progress","generated":2,"total":5}
...

data: {"type":"done","exercises":[...],"batch_id":"uuid"}
```

**exercise 事件中的 exercise 对象结构：**
```json
{
  "id": "uuid",
  "question": "题目内容",
  "question_type": "choice",
  "options": ["A. 选项1", "B. 选项2"],
  "answer": null,
  "analysis": null,
  "difficulty": "medium",
  "knowledge_points": ["知识点"],
  "subject": "语文",
  "grade": "七年级"
}
```

**注意**：生成阶段的 `answer` 和 `analysis` 应为 `null`（防止前端泄露答案）。答案在批改阶段返回。

---

### 6.2 批改作答

```
POST /api/v1/exercises/grade
认证：是
```

**Request:**
```json
{
  "batch_id": "uuid",
  "answers": [
    { "exercise_id": "uuid-1", "user_answer": "A" },
    { "exercise_id": "uuid-2", "user_answer": "便要还家" }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| batch_id | string | 是 | 习题批次 ID |
| answers | array | 是 | 作答列表 |
| answers[].exercise_id | string | 是 | 习题 ID |
| answers[].user_answer | string | 是 | 用户答案 |

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total_score": 85.0,
    "correct_count": 4,
    "total_count": 5,
    "results": [
      {
        "exercise_id": "uuid-1",
        "is_correct": true,
        "score": 20.0,
        "correct_answer": "A",
        "analysis": "本题考查文言实词...",
        "error_reason": null,
        "related_knowledge": ["文言实词"]
      },
      {
        "exercise_id": "uuid-3",
        "is_correct": false,
        "score": 11.0,
        "correct_answer": "表达了作者对理想社会的向往和对现实社会的不满",
        "analysis": "答题要点：1.向往理想社会 2.对现实不满",
        "error_reason": "遗漏了'对现实不满'这一要点",
        "related_knowledge": ["桃花源记中心思想"]
      }
    ]
  }
}
```

**注意**：此时 `results[].correct_answer` 和 `results[].analysis` 才返回真实值。

---

### 6.3 做题历史

```
GET /api/v1/exercises/history?page=1&page_size=20
认证：是
```

**Response (200):** 返回分页对象，`items` 为 `IExerciseBatch[]`：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "uuid",
        "exercises": [ ... ],
        "grade_result": { ... },
        "created_at": "2026-07-03T10:00:00Z"
      }
    ],
    "total": 25,
    "page": 1,
    "page_size": 20,
    "total_pages": 2
  }
}
```

---

### 6.4 单次练习详情

```
GET /api/v1/exercises/batches/{batch_id}
认证：是
```

**Response (200):** 返回完整 `IExerciseBatch` 对象（同 §6.3 的 item）。

---

### 6.5 删除练习记录

```
DELETE /api/v1/exercises/batches/{batch_id}
认证：是
```

**Response (200):**
```json
{ "code": 0, "message": "删除成功", "data": null }
```

---

## 七、知识图谱模块（PBI_11）

### 7.1 生成知识图谱

```
POST /api/v1/knowledge/graph
认证：是
```

**Request:**
```json
{
  "source_type": "subject",
  "source": "语文-七年级-文言文",
  "file_id": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_type | string | 是 | `subject` / `chapter` / `file` |
| source | string | 是 | 学科名/章节名 |
| file_id | string\|null | 否 | source_type=file 时传入 |

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "graph_id": "uuid",
    "title": "七年级文言文知识图谱",
    "nodes": [
      { "id": "n1", "label": "文言文", "type": "category", "x": 400, "y": 50 },
      { "id": "n2", "label": "桃花源记", "type": "article", "x": 250, "y": 200 }
    ],
    "edges": [
      { "source": "n1", "target": "n2", "relation": "包含课文" }
    ]
  }
}
```

| 节点 type 枚举 | 说明 |
|---------------|------|
| `category` | 顶层分类（如"文言文"） |
| `article` | 具体课文/章节 |
| `knowledge` | 知识点 |

**注意**：`x` / `y` 为初始布局坐标（后端可给默认值，前端 ECharts 会自动调整）。

---

### 7.2 图谱列表

```
GET /api/v1/knowledge/graphs?page=1&page_size=20
认证：是
```

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "uuid",
        "title": "七年级文言文知识图谱",
        "node_count": 12,
        "edge_count": 15,
        "source_type": "subject",
        "created_at": "2026-07-03T10:00:00Z"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
}
```

**注意**：`node_count` 和 `edge_count` 必须返回，前端用于列表展示。

---

### 7.3 查看图谱

```
GET /api/v1/knowledge/graphs/{graph_id}
认证：是
```

**Response (200):** 返回完整 `IKnowledgeGraph` 对象（同 §7.1 响应 data），包含所有节点和边。

---

### 7.4 节点详情

```
GET /api/v1/knowledge/graphs/{graph_id}/node/{node_id}
认证：是
```

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "node_id": "n2",
    "label": "桃花源记",
    "description": "《桃花源记》是东晋文学家陶渊明的代表作之一...",
    "examples": [
      "解释下列加点词的意思：①缘溪行（沿着）②仿佛若有光（隐隐约约）",
      "翻译：阡陌交通，鸡犬相闻 → 田间小路交错相通..."
    ],
    "common_mistakes": ["实词'缘'误译为'缘分'", "把'交通'理解为现代交通"],
    "related_nodes": [
      { "id": "n1", "label": "文言文", "relation": "属于" },
      { "id": "n5", "label": "实词", "relation": "重点考查" }
    ]
  }
}
```

---

### 7.5 删除图谱

```
DELETE /api/v1/knowledge/graphs/{graph_id}
认证：是
```

**Response (200):**
```json
{ "code": 0, "message": "删除成功", "data": null }
```

---

### 7.6 导出图谱为图片

```
POST /api/v1/knowledge/graphs/{graph_id}/export
认证：是
```

**Response (200):**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "url": "https://cdn.zhiyi.com/exports/graph-uuid.png"
  }
}
```

**简化替代方案**：如果后端不方便生成 PNG，可直接返回图谱 JSON 数据，前端用 ECharts 的 `getDataURL()` 在前端完成导出。此接口可先返回：
```json
{ "code": 0, "message": "ok", "data": { "url": null } }
```

---

## 八、接口优先级与开发顺序

### 第一阶段（Sprint 1 前期 — 核心闭环）

| 优先级 | 模块 | 端点 | 类型 |
|--------|------|------|------|
| P0 | 健康检查 | `GET /api/v1/health` | REST |
| P0 | M1 认证 | `POST /auth/register` | REST |
| P0 | M1 认证 | `POST /auth/login` | REST |
| P0 | M1 认证 | `POST /auth/reset-password` | REST |
| P0 | M1 认证 | `POST /auth/reset-password/verify` | REST |
| P0 | M1 认证 | `GET /users/profile` | REST |
| P0 | M1 认证 | `PUT /users/profile` | REST |
| P1 | M1 认证 | `GET /users/dashboard` | REST |
| P1 | M2 Agent | `POST /agent/chat` | **SSE** |
| P1 | M2 Agent | `GET /agent/sessions` | REST |
| P1 | M2 Agent | `GET /agent/sessions/{id}` | REST |
| P1 | M2 Agent | `DELETE /agent/sessions/{id}` | REST |
| P1 | M3 总结 | `POST /summaries/generate` | **SSE** |
| P1 | M3 总结 | `GET /summaries` | REST |
| P1 | M3 总结 | `GET /summaries/{id}` | REST |
| P1 | M3 总结 | `DELETE /summaries/{id}` | REST |

### 第二阶段（Sprint 2）

| 模块 | 端点 | 类型 |
|------|------|------|
| M4 文件 | `POST /files/upload` | REST (multipart) |
| M4 文件 | `GET /files` | REST |
| M4 文件 | `GET /files/{id}/status` | REST |
| M4 文件 | `POST /files/{id}/reparse` | REST |
| M4 文件 | `DELETE /files/{id}` | REST |
| M5 习题 | `POST /exercises/generate` | **SSE** |
| M5 习题 | `POST /exercises/grade` | REST |
| M5 习题 | `GET /exercises/history` | REST |
| M5 习题 | `GET /exercises/batches/{id}` | REST |
| M5 习题 | `DELETE /exercises/batches/{id}` | REST |
| M6 图谱 | `POST /knowledge/graph` | REST |
| M6 图谱 | `GET /knowledge/graphs` | REST |
| M6 图谱 | `GET /knowledge/graphs/{id}` | REST |
| M6 图谱 | `GET /knowledge/graphs/{id}/node/{id}` | REST |
| M6 图谱 | `DELETE /knowledge/graphs/{id}` | REST |
| M6 图谱 | `POST /knowledge/graphs/{id}/export` | REST |

---

## 九、错误码速查

| code | HTTP | 说明 | 触发场景 |
|------|------|------|---------|
| 0 | 200 | 成功 | |
| 40001 | 400 | 参数校验失败 | 字段缺失/格式错误 |
| 40002 | 400 | 文件格式不支持 | 上传了不支持的格式 |
| 40003 | 400 | 文件大小超限 | > 50 MB |
| 40101 | 401 | Token 过期 | |
| 40102 | 401 | Token 无效 | 伪造/已撤销 |
| 40301 | 403 | 无权操作 | 操作他人资源 |
| 40401 | 404 | 用户不存在 | |
| 40402 | 404 | 资源不存在 | |
| 40901 | 409 | 邮箱/手机号已被注册 | |
| 42901 | 429 | 请求频率超限 | |
| 50001 | 500 | 服务器内部错误 | |
| 50002 | 500 | LLM 服务调用失败 | |
| 50003 | 500 | 文件解析失败 | |

---

> **生成依据**：此文档基于 `D:\VScode\zy-fe\frontend\src\api\modules\*.ts` 和 所有 `.vue` 文件中实际调用的 API 端点整理而成，与前端代码 100% 对应。  
> **前端类型参照**：所有 Request/Response 的字段名和类型与 `src/types/index.ts` 完全对齐。
