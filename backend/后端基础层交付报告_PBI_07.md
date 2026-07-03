# PBI_07 后端基础设施建设说明

> **项目**：智翼（ZhiYi）AI 学习助手平台  
> **创建日期**：2026-07-03  
> **对应文档**：`智翼平台开发规范与接口文档.md` + `智翼平台模块分组与验收方案.md`  
> **状态**：✅ 已完成

---

## 一、项目位置

```
D:\VScode\zy-be\backend\
```

共创建 **15 个目录、57 个文件**。

---

## 二、完整目录结构

```
backend/
├── .env.example                          # 环境变量模板
├── pyproject.toml                        # 项目元数据 + ruff/black/pytest 配置
├── requirements.txt                      # pip 依赖清单
├── Dockerfile                            # Docker 镜像
├── docker-compose.yml                    # MySQL + Redis + Backend 编排
├── zy.sql                                 # MySQL 建表脚本（9 张表）
├── alembic.ini                           # Alembic 数据库迁移配置
│
├── alembic/
│   ├── env.py                            # 异步 Alembic 环境配置
│   ├── script.py.mako                    # 迁移脚本模板
│   └── versions/                         # 迁移版本（当前为空）
│
├── app/
│   ├── __init__.py
│   ├── main.py                           # FastAPI 应用入口 + 生命周期管理
│   │
│   ├── core/                             # ═══ 基础设施核心层 ═══
│   │   ├── __init__.py
│   │   ├── config.py                     # pydantic-settings 配置管理（全部环境变量）
│   │   ├── security.py                   # JWT 令牌生成/验证 + bcrypt 密码哈希
│   │   ├── database.py                   # SQLAlchemy 2.0 异步引擎 + 会话工厂 + Base
│   │   └── redis.py                      # Redis 异步连接池管理
│   │
│   ├── api/                              # ═══ API 路由层 ═══
│   │   ├── __init__.py
│   │   ├── deps.py                       # 依赖注入（get_db, get_current_user, get_optional_user）
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py                 # ★ 路由聚合 + /api/v1/health 健康检查
│   │       ├── auth.py                   # 占位 — PBI_01 Sprint 1
│   │       ├── users.py                  # 占位 — PBI_01 Sprint 1
│   │       ├── agent.py                  # 占位 — PBI_04/PBI_12 Sprint 1
│   │       ├── summary.py                # 占位 — PBI_06 Sprint 1
│   │       ├── exercises.py              # 占位 — PBI_08/09/10 Sprint 2
│   │       ├── files.py                  # 占位 — PBI_05 Sprint 2
│   │       └── knowledge.py              # 占位 — PBI_11 Sprint 2
│   │
│   ├── models/                           # ═══ 数据模型层（9 张表） ═══
│   │   ├── __init__.py                   # 导入所有模型供 Alembic 自动发现
│   │   ├── user.py                       # users + learning_profiles
│   │   ├── chat.py                       # chat_sessions + chat_messages
│   │   ├── summary.py                    # summaries
│   │   ├── file.py                       # uploaded_files
│   │   ├── exercise.py                   # exercises + exercise_attempts
│   │   └── knowledge.py                  # knowledge_graphs
│   │
│   ├── schemas/                          # ═══ Pydantic v2 请求/响应模型 ═══
│   │   ├── __init__.py
│   │   ├── common.py                     # 统一响应格式 + 错误码枚举 + 分页工具
│   │   ├── user.py                       # 注册/登录/仪表盘 Schema
│   │   ├── agent.py                      # Agent 对话 Schema
│   │   ├── summary.py                    # 课文总结 Schema
│   │   ├── exercise.py                   # 习题生成/批改 Schema
│   │   ├── file.py                       # 文件上传/状态 Schema
│   │   └── knowledge.py                  # 知识图谱 Schema
│   │
│   ├── services/                         # ═══ 业务逻辑层 ═══
│   │   ├── __init__.py
│   │   ├── user_service.py               # ✅ 已实现骨架（注册/登录/JWT/仪表盘）
│   │   ├── agent_service.py              # 占位 — Sprint 1
│   │   ├── summary_service.py            # 占位 — Sprint 1
│   │   ├── exercise_service.py           # 占位 — Sprint 2
│   │   ├── file_service.py               # 占位 — Sprint 2
│   │   └── knowledge_service.py          # 占位 — Sprint 2
│   │
│   ├── ai/                               # ═══ AI 模块 ═══
│   │   ├── __init__.py
│   │   ├── llm_client.py                 # LLM 客户端（OpenAI 兼容，支持流式+重试）
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── tools.py                  # AgentTool 定义 + ToolRegistry 注册中心
│   │   │   └── orchestrator.py           # Agent 编排器（意图解析 + SSE 流式执行）
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── summary.py                # 课文总结 Prompt（精简/详细双模式）
│   │       ├── exercise_gen.py           # 习题生成 Prompt（5 种题型）
│   │       └── grading.py                # 批改 Prompt（分题型评分规则）
│   │
│   └── middleware/                       # ═══ 中间件 ═══
│       ├── __init__.py
│       ├── cors.py                       # CORS 跨域配置
│       └── logging.py                    # loguru 请求日志中间件
│
└── tests/
    ├── __init__.py
    ├── conftest.py                       # pytest 异步 Fixtures（SQLite + httpx）
    └── api/
        ├── __init__.py
        └── test_health.py                # 健康检查端点测试
```

---

## 三、技术选型对照

| 类别 | 选型 | 说明 |
|------|------|------|
| Web 框架 | FastAPI 0.110+ | 异步支持，自动 OpenAPI |
| 语言 | Python 3.12+ | 完整类型注解 |
| ORM | SQLAlchemy 2.0 (async) | `asyncmy` 驱动 |
| 迁移 | Alembic | 已配置异步引擎 |
| 校验 | Pydantic v2 | 与 FastAPI 深度集成 |
| 认证 | JWT (python-jose) + bcrypt | `passlib` 哈希 |
| 缓存 | Redis (aioredis) | 连接池单例 |
| 数据库 | MySQL 8.0 | InnoDB, utf8mb4, JSON 原生支持 |
| AI 流式 | SSE + httpx | `sse-starlette` 备用 |
| LLM | OpenAI 兼容 API | 封装重试 + 流式 |
| 日志 | loguru | 请求中间件自动记录 |
| 测试 | pytest + httpx | 异步测试，SQLite 内存库 |
| 代码规范 | ruff + black | pyproject.toml 已配置 |

---

## 四、关键设计决策

### 4.1 统一响应格式

与文档附录 A.1 一致：

```json
// 成功
{ "code": 0, "message": "ok", "data": { ... } }

// 错误
{ "code": 40001, "message": "参数校验失败", "detail": null }
```

### 4.2 错误码

`app/schemas/common.py` 中 `ErrorCode` 类包含全部 15 个错误码，对照文档附录 A.3：

| code | 说明 |
|------|------|
| 0 | 成功 |
| 40001 | 参数校验失败 |
| 40002 | 文件格式不支持 |
| 40003 | 文件大小超限 |
| 40101 | Token 过期 |
| 40102 | Token 无效 |
| 40301 | 无权操作 |
| 40401 | 用户不存在 |
| 40402 | 资源不存在 |
| 40901 | 邮箱/手机号已被注册 |
| 42901 | 请求频率超限 |
| 50001 | 服务器内部错误 |
| 50002 | LLM 服务调用失败 |
| 50003 | 文件解析失败 |

### 4.3 分层架构

```
Router  →  Service  →  Model
(路由)     (业务)      (数据)

每个端点严格遵循此三层调用链
```

### 4.4 API 路由组织

```
/api/v1/health              — 健康检查 ✅ 已可用
/api/v1/auth/*              — 认证模块（待实现）
/api/v1/users/*             — 用户模块（待实现）
/api/v1/agent/*             — AI Agent（待实现）
/api/v1/summaries/*         — 课文总结（待实现）
/api/v1/exercises/*         — 习题模块（待实现）
/api/v1/files/*             — 文件管理（待实现）
/api/v1/knowledge/*         — 知识图谱（待实现）
```

### 4.5 Agent 工具注册框架

`app/ai/agent/tools.py` 实现了文档 §4.2 的 `AgentTool` 接口：

```python
@dataclass
class AgentTool:
    name: str           # 工具唯一标识，如 "text_summary"
    description: str    # LLM 意图匹配描述
    parameters: dict    # JSON Schema 参数定义
    handler: Callable   # 实际执行函数
```

全局 `ToolRegistry` 管理所有注册工具，支持导出 OpenAI function calling 格式。

### 4.6 SSE 流式事件格式

编排器 `run_stream()` 按文档 §5.2.1 格式输出：

```
data: {"type":"thought","step":1,"title":"需求分析","content":"..."}
data: {"type":"content","chunk":"回复文本..."}
data: {"type":"done","session_id":"uuid","usage":{...}}
data: {"type":"error","message":"错误信息"}
```

---

## 五、数据库表

与文档 §4.1 完全对应，共 9 张表（建表脚本：`zy.sql`）：

| 表名 | 模型文件 | 对应 PBI |
|------|----------|----------|
| `users` | `app/models/user.py` | PBI_01 |
| `learning_profiles` | `app/models/user.py` | PBI_01 |
| `chat_sessions` | `app/models/chat.py` | PBI_04 |
| `chat_messages` | `app/models/chat.py` | PBI_04, PBI_12 |
| `summaries` | `app/models/summary.py` | PBI_06 |
| `uploaded_files` | `app/models/file.py` | PBI_05 |
| `exercises` | `app/models/exercise.py` | PBI_08 |
| `exercise_attempts` | `app/models/exercise.py` | PBI_09, PBI_10 |
| `knowledge_graphs` | `app/models/knowledge.py` | PBI_11 |

---

## 六、快速启动

### 前置条件

- Python 3.12+
- Docker Desktop（或本地安装 MySQL 8.0 + Redis 7）

### 步骤

```bash
cd D:\VScode\zy-be\backend

# 1. 复制并编辑环境变量（务必修改 SECRET_KEY 和 LLM_API_KEY）
cp .env.example .env

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动 MySQL + Redis（Docker 方式）
docker compose up -d mysql redis

# 5. 执行数据库迁移（或直接导入 zy.sql）
alembic upgrade head
# 备选：mysql -u root -p zhiyi < ../zy.sql

# 6. 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 7. 验证
curl http://localhost:8000/api/v1/health
# → {"status":"ok","service":"ZhiYi API"}

# 8. 查看 API 文档
# 浏览器打开 http://localhost:8000/docs    (Swagger)
# 浏览器打开 http://localhost:8000/redoc   (ReDoc)
```

### 环境变量说明

| 变量 | 说明 | 必填 |
|------|------|------|
| `SECRET_KEY` | JWT 签名密钥，至少 32 字符 | ✅ |
| `DATABASE_URL` | MySQL 连接串 | ✅ |
| `REDIS_URL` | Redis 连接串 | ✅ |
| `LLM_API_KEY` | LLM API 密钥 | AI 功能需要 |
| `LLM_API_BASE_URL` | LLM API 地址 | 默认 OpenAI |
| `LLM_MODEL` | 模型名称 | 默认 gpt-4o |
| `CORS_ORIGINS` | 前端地址白名单 | 默认 localhost:5173 |
| `UPLOAD_DIR` | 文件上传目录 | 默认 ./uploads |
| `MAX_FILE_SIZE_MB` | 上传大小限制 | 默认 50 |

---

## 七、后续开发指引

按 `模块分组与验收方案.md` 顺序：

### 第一阶段：Sprint 1 前期

| 模块 | PBI | 文件 | 状态 |
|------|-----|------|------|
| M1 认证 | PBI_01 | `api/v1/auth.py` + `api/v1/users.py` | 🔴 待实现 |
| M2 AI Agent | PBI_04, PBI_12 | `api/v1/agent.py` + `ai/agent/` | 🔴 待实现 |
| M3 课文总结 | PBI_06 | `api/v1/summary.py` + `ai/prompts/summary.py` | 🔴 待实现 |

### 第二阶段：Sprint 2

| 模块 | PBI | 文件 | 状态 |
|------|-----|------|------|
| M4 文件管理 | PBI_05 | `api/v1/files.py` | 🔴 待实现 |
| M5 习题模块 | PBI_08/09/10 | `api/v1/exercises.py` | 🔴 待实现 |
| M6 知识图谱 | PBI_11 | `api/v1/knowledge.py` | 🔴 待实现 |

### 激活路由方法

在 `app/api/v1/router.py` 中取消对应行注释即可：

```python
# 当前状态（注释状态）：
# from app.api.v1.auth import router as auth_router
# api_router.include_router(auth_router, prefix="/auth", tags=["认证"])

# 开发时取消注释：
from app.api.v1.auth import router as auth_router
api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
```

### Agent 工具注册示例

新模块接入 Agent 时，按如下方式注册工具：

```python
from app.ai.agent.tools import AgentTool, tool_registry

summary_tool = AgentTool(
    name="text_summary",
    description="对课文内容进行结构化总结，提取知识点",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "课文原文"},
            "mode": {"type": "string", "enum": ["brief", "detailed"]}
        },
        "required": ["content"]
    },
    handler=your_summary_function
)

tool_registry.register(summary_tool)
```

---

## 八、测试

```bash
# 运行全部测试
pytest

# 带覆盖率报告
pytest --cov=app --cov-report=html

# 运行单个测试文件
pytest tests/api/test_health.py -v
```

---

## 九、代码规范

已配置 `ruff`（linter）和 `black`（formatter），保存前请运行：

```bash
# 代码检查
ruff check app/

# 代码格式化
black app/
```

---

> **维护约定**：后端每次新增/修改 API，应同步更新 `智翼平台开发规范与接口文档.md` 的对应接口章节和 Schema。  
> **文档版本**：v1.0 | 2026-07-03
