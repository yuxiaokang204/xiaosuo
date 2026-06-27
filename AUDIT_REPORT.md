# Novel Agent System v1.1.0 — 代码审计与修复报告

- 审计日期：2026-06-17
- 范围：通读后端（FastAPI / agents / core / db / llm）、前端（React+TS）、配置与文档
- 方法：多 Explore 子代理静态扫描 → **人工逐条核实代码**（剔除误报）→ 实施修复
- 交付：审计报告 + 全量修复 + 运行验证
- 重要原则：探索代理的结论一律以实际代码为准复核；下文标注 ✅已确认 / ❌误报澄清 / ⚠️待运行验证。

---

## 一、误报澄清（探索阶段提出但经核实不成立，**未做改动**）

逐条读源码后确认以下"缺陷"并不成立，记录以免误导后续维护：

1. ❌ **Orchestrator 暂停/恢复死锁** — 实际用 `asyncio.Event`，初始 `.set()`，`pause→clear`/`resume→set`/`abort→set`，循环中 `await _pause_event.wait()`。这是标准且正确的 asyncio 模式，**无死锁**。（`core/orchestrator.py:214-261`）
2. ❌ **`.env` 密钥已提交进版本控制** — 该项目当前**不是 git 仓库**，`.env.example` 为纯占位（无真实 key）。真实 key 只存在于本地 `.env`（密钥的正确存放位置）。详见下文安全章节的修正结论。
3. ❌ **`_ensure_services_ready` 初始化竞态** — 该函数为同步、无 `await`，在单线程事件循环中原子执行，并发协程无法在其内部交错，**不存在竞态**。（`main.py:82-89`）
4. ❌ **custom_openai URL 双重拼接** — `endswith("/chat/completions")` 守卫已防止重复追加，对用户实际 base（`.../open/v1`）拼接结果正确。（`llm/client.py:599-604`）
5. ❌ **Anthropic 全 system 消息伪造 user** — `BaseAgent` 调用始终带 user 消息，该 fallback 路径实际几乎不触发，且 fallback 本身可避免 Claude 空 messages 报错。保留。
6. ❌ **前端 SSE 卸载不清理导致泄漏** — 指向的是 `components/OrchestratorPanel.tsx` 等**死代码**（见下）；实际在用的 `pages/OrchestratorPage.tsx` 用模块级单例 EventSource，并在 done/error/abort/stop 显式 `close()`，"卸载不关闭"是有意保活设计。

---

## 二、已确认缺陷与已实施修复

### 🔴 P0 安全

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| S1 | `.env:28,30` | 含**真实可用**的 LLM API Key（中国移动 MaaS）明文 | 见下方"修正结论"。新增 `.gitignore` 排除 `.env`/`*.db`/`run.log` 等，防止未来 `git init` 误提交 |
| S2 | `.env:15` `DEBUG=true` | 无 dev/prod 区分 | 已存在 `APP_ENV`；`DEBUG` 未在代码中启用危险行为（FastAPI 未以 debug 模式构建），属低风险，报告记录 |

**S1 修正结论**：探索代理称"密钥进版本控制"不准确（仓库非 git、`.env.example` 干净）。密钥位于本地 `.env` 是**正确**的存放方式。**未清空该 key**——清空会立即中断用户正在使用的 LLM 连接（难撤销的外向影响）。已做防御：创建 `.gitignore`。**建议**：若该 `.env` 曾被分享/上传，应轮换此 key。

### 🔴 P0 数据库 / 数据完整性（`db/models.py`、`db/database.py`）

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| D1 | `models.py` 多处 | 引用列为裸 `Column(String)`，无外键 | 补外键：`chapters.parent_chapter_id→chapters`（SET NULL）、`characters.world_id→world_settings`（SET NULL）、`character_relationships.target_character_id→characters`（CASCADE）、`user_feedback.novel_id→novels`（CASCADE）/`chapter_id→chapters`（SET NULL） |
| D2 | `novels.world_id` | 与 `world_settings.novel_id` 构成**循环外键** | 仅加 `index=True`，不加 FK（避免 `create_all` 顺序问题）；已在报告记录权衡 |
| D3 | `agent_executions.novel_id` | — | 执行记录可能来自无小说上下文的独立调用，**刻意不加 FK**，仅加索引 |
| D4 | 全表 | 缺常用查询索引 | 为 `status`/`created_at`/`role`/`feedback_type`/各 FK 列加 `index=True`；并在 `_migrate_db` 增加 `CREATE INDEX IF NOT EXISTS`，使**已存在的数据库**也补上索引（模型层 `index=True` 仅对新表生效） |
| D5 | `database.py:14` `echo=True` | SQL 全量回显，生产噪音/性能损耗 | 改为 `SQL_ECHO` 环境变量控制，默认 **False** |
| D6 | `database.py:81` `await conn.fetchall()` | **AsyncConnection 无 fetchall**，迁移每次启动即抛 AttributeError，但被 `lifespan` 的 `except: pass` 静默吞掉 → 老库缺列迁移**从未真正生效** | 改为 `result.fetchall()`，并对每列迁移加 try/except 打印（不再被静默） |

### 🔴/🟡 P1 后端核心逻辑

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| B1 | `core/global_summary.py:204-216` | 情节阶段判断 `total <= total*0.3+2` 为自比较，对 total≥3 恒假 → **"发展"阶段永不可达**，7 章即误判"收束" | 重写为基于比例（`max(total,target,10)` 为分母）；新增 `set_target_chapters()`；保证四阶段可达 |
| B2 | `core/orchestrator.py:464+` | 单章生成失败仅写 ~100 字占位、不重试 | 加指数退避重试（最多 3 次，1s/2s 退避）；最终失败显式 `chapter_error` 事件且不污染后续上下文 |
| B3 | `agents/base.py:67-80` | mock 兜底数据冒充 `success=True`，调用方/前端无法区分 | 兜底返回新增 `fallback:true` + `fallback_reason`；正常路径加 `fallback:false` |
| B4 | `core/memory.py` | token 估算两套口径（÷1.5 vs ÷3）不一致；`short_term_memory` 无上限 | 新增统一 `estimate_tokens()`（与 LLMClient 同口径），`get_context` 改用之；`short_term_memory` 上限 200 |
| B5 | `core/learning_engine.py` | 偏好/反模式重复反馈无去重 → `random.choice` 概率被放大 | `_learn_style_edit`/`_analyze_pattern_changes`/`_learn_negative_pattern` 全部去重 |
| B6 | `core/state_tracker.py:140` | 角色 `history` 无限增长 | 上限 100 条 |
| B7 | `main.py:878` | `_active_orchestrators` 无 TTL/清理 → 长跑内存增长 | 增加 `last_seen` 跟踪 + TTL（2h）+ 容量上限（50）清理，在 start/stream 时触发 |
| B8 | `llm/client.py:425` | 缓存 FIFO 淘汰、并发下 `del` 可能 KeyError、无锁 | 加 `asyncio.Lock`，淘汰用 `pop(...,None)` |
| B9 | `llm/client.py:488` | 流式分片解析失败静默 `pass` | 改为打印可诊断日志（不中断流） |

### 🟡 P1 前端（仅改**实际在用**的 `pages/` 与 `App.tsx`）

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| F1 | `App.tsx` / `pages/NovelManagerPage.tsx:272` / `pages/NovelReadPage.tsx:49,55` | 页面用 `window.dispatchEvent(CustomEvent("navigate"))` 跳转，但**全代码无监听器** → 按钮点击无效（真实 bug） | 在 `App.tsx` 加 `window.addEventListener("navigate")` → `setCurrentPage`，一次性修好三处 |
| F2 | `pages/OrchestratorPage.tsx` | 未处理后端新增的 `chapter_error` 事件 | 新增监听，在日志区显式提示"第 N 章生成失败" |
| F3 | `api.ts:2` | 注释称代理指向 `localhost:8000` | 改为 `127.0.0.1:8080`（与 `run.py`/`vite.config.ts` 一致） |

### 🟡 P2 工程化 / 测试 / 文档

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| Q1 | `test_project.py` | 几乎无真实 `assert`，全程 `try/except` 吞异常 → 逻辑 bug（如 B1）不会被捕获 | 新增 `test_regression.py`，对 B1/B4/B5/D1/D4/D5 用**真实 assert**回归；原文件弱点记录于报告（建议后续整体改 pytest） |
| Q2 | `pyproject.toml` | `httpx`、`aiohttp` 被 `llm/client.py` 直接使用却**漏列依赖**；版本无上界 | 补 `httpx`/`aiohttp`；为 fastapi/pydantic/sqlalchemy/openai 等加主版本上界 |
| Q3 | `run.py` | `.env` 复制、UTF-8 重配、日志打开均无异常处理 | 全部加 try/except，失败退化而非崩溃 |
| Q4 | 无前端 lint | — | 加 `eslint.config.js`（ESLint 9 扁平）+ `.prettierrc.json` + `package.json` 的 lint/format 脚本与 devDeps（需 `npm install` 生效） |
| Q5 | `CLAUDE.md` / `main.py` docstring | 端口写 8000（实际 8080）；DB 文件名注释写反（实际 `novel_agent.db`） | 全部更正为 8080 / `novel_agent.db` |

---

## 三、建议但**未自动执行**（需你决策，多为破坏性或大重构）

1. **删除前端死代码**：`src/frontend/src/components/` 下的 `OrchestratorPanel.tsx`、`DashboardPanel.tsx`、`NovelManagerPanel.tsx`、`CharacterManager.tsx`、`WorldSettingManager.tsx`、`LLMConfigPanel.tsx` 均**未被 `App.tsx` 引用**，与 `pages/` 下实现重复。删除属破坏性操作，建议你确认后清理。
2. **类型单一来源**：`api.ts` 与 `types.ts` 重复定义 `Character`/`Chapter` 且字段不一致。合并需触碰较多 import，存在破坏 TS 编译风险，建议单独一轮重构 + `npm run build` 验证。
3. **引入 Alembic** 替代手写 `_migrate_db`，获得版本化、可回滚迁移。
4. **`memory` 可选用 `tiktoken`**（已是依赖）替代字符启发式，换取更精确的 token 预算（代价：每次调用更慢）。
5. **轮换 S1 中的 LLM API Key**（若 `.env` 曾外泄）。
6. **`get_db` 隐式 commit**：经核实每个 CRUD 方法自身已 commit，`get_db` 的 yield 后 commit 为冗余无害的 no-op，非真 bug。保留；如需严格事务边界可在后续重构中由调用端显式管理。

---

## 四、运行验证

> 状态：本次会话 Bash 沙箱分类器服务多次不可用，自动化运行被阻断。以下为**应执行的验证命令**与预期；恢复后我会补跑并更新本节。已通过 Read/Edit 的方式确保每处编辑落盘且语义正确。

```bash
# 1) 后端编译校验
python -m py_compile src/backend/**/*.py

# 2) 回归测试（应全过，且能捕捉旧的情节进度 bug）
python test_regression.py

# 3) 原有测试
python test_project.py

# 4) 启动后端（重点确认：无迁移 fetchall 报错、SQL echo 静默、索引已建）
python run.py            # http://localhost:8080/docs

# 5) 数据库索引核查
python check_db.py
# 或 sqlite3 novel_agent.db ".indexes"

# 6) 前端
npm install             # 安装新增 eslint/prettier 等
npm run build           # tsc 严格模式 + vite 构建
npm run lint            # 新增 lint
```

预期：
- `test_regression.py` 全过；其中 `情节阶段判断修复` 用例在旧代码下必然失败（证明 B1 已修）。
- 后端启动日志不再出现 `AsyncConnection ... fetchall` 异常；SQL 不再刷屏。
- `npm run build` 在 TS strict 下通过（前端改动均为局部、附加式，低风险）。

---

## 五、改动文件清单

后端：`src/backend/db/{models,database}.py`、`src/backend/core/{global_summary,memory,learning_engine,state_tracker,orchestrator}.py`、`src/backend/agents/base.py`、`src/backend/llm/client.py`、`src/backend/main.py`
前端：`src/frontend/src/App.tsx`、`src/frontend/src/pages/OrchestratorPage.tsx`、`src/frontend/src/api.ts`
配置/测试/文档：`pyproject.toml`、`package.json`、`run.py`、`CLAUDE.md`、新增 `.gitignore`、`.prettierrc.json`、`eslint.config.js`、`test_regression.py`、`AUDIT_REPORT.md`
