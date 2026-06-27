# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**小说创作Agent系统** (Novel Agent System) — An AI-powered novel creation platform with multi-agent collaboration. It uses 6 specialized Skills to help users create complete novels from scratch, covering outline generation, world-building, character design, drafting, editing, and quality review.

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy, SQLite (aiosqlite), OpenAI SDK
- **Frontend**: React 18, TypeScript, Vite
- **Build**: Vite 5 (frontend), hatchling (Python)
- **LLM Support**: 10+ providers via abstraction layer (mock, openai, deepseek, anthropic, google, qwen, moonshot, ollama, openrouter, custom_openai)

## Directory Structure

```
├── src/
│   ├── backend/                  # FastAPI backend
│   │   ├── main.py               # FastAPI app entry (lifespan, routes, SSE streaming)
│   │   ├── agents/               # 6 Skills
│   │   │   ├── base.py           # BaseAgent abstract class
│   │   │   ├── prompts.py        # Shared skill prompts/templates
│   │   │   ├── outline_agent.py  # 故事架构师: Chapter-by-chapter outlines
│   │   │   ├── draft_agent.py    # 专业写手: Generate chapter content
│   │   │   ├── edit_agent.py     # 文风精修师: Edit/polish chapter content
│   │   │   ├── review_agent.py   # Quality review & scoring
│   │   │   ├── world_agent.py    # 世界观构建师: World-building design
│   │   │   ├── character_agent.py # 角色塑造师: Character design
│   │   │   ├── style_agent.py    # 开篇钩子师: Opening hook design
│   │   │   └── plot_agent.py     # Plot analysis & progression
│   │   ├── core/                 # Core system logic
│   │   │   ├── orchestrator.py   # NovelOrchestrator state machine (8-stage workflow)
│   │   │   ├── memory.py         # 3-layer memory system (working/short/long-term)
│   │   │   ├── learning_engine.py # User feedback learning system
│   │   │   ├── agent_registry.py     # Agent registration & discovery
│   │   │   ├── agent_registry_initializer.py # Bootstrap agent registration
│   │   │   ├── agent_executor.py     # Agent execution tracking
│   │   │   ├── consistency_checker.py # Cross-chapter consistency validation
│   │   │   ├── state_tracker.py      # Character/location state tracking
│   │   │   ├── global_summary.py     # Global context summarization
│   │   │   └── chapter_pipeline.py   # Chapter processing pipeline
│   │   ├── db/                   # Database layer
│   │   │   ├── models.py         # SQLAlchemy ORM models
│   │   │   ├── database.py       # DB connection setup
│   │   │   └── crud.py           # CRUD operations
│   │   ├── models/               # Pydantic schemas (40+ request/response models)
│   │   │   └── schemas.py
│   │   └── llm/                  # LLM client abstraction
│   │       └── client.py         # Multi-provider LLM interface
│   └── frontend/                 # React + TypeScript frontend
│       └── src/
│           ├── main.tsx          # React entry point
│           ├── App.tsx           # Root component
│           ├── api.ts            # API client + TypeScript types
│           ├── types.ts          # TS interfaces
│           └── components/       # UI components
│               ├── DashboardPanel.tsx
│               ├── NovelManagerPanel.tsx
│               ├── OrchestratorPanel.tsx
│               ├── LLMConfigPanel.tsx
│               ├── CharacterManager.tsx
│               ├── WorldSettingManager.tsx
│               └── NovelEditor.tsx
├── run.py                        # Backend startup script (TeeOutput, uvicorn)
├── start.sh                      # Linux/Mac startup script
├── test_project.py               # Comprehensive test script (111 tests across 7 modules)
├── check_db.py                   # Database validation utility
├── pyproject.toml                # Python project config (hatchling)
├── package.json                  # Node.js frontend config
├── vite.config.ts                # Vite config (proxy /api → backend:8080)
├── tsconfig.json                 # TypeScript config (strict mode)
├── .env.example                  # Environment variables template
└── PROJECT_ARCHITECTURE.md       # Detailed architecture documentation
```

## Key Architecture Concepts

### 6 Specialized Skills
Each skill inherits from `BaseAgent` and implements `async process(context: Dict) -> Dict`. They are registered via `AgentRegistryInitializer` at startup:

| Skill | Capability | Purpose |
|-------|-----------|---------|
| OutlineAgent (故事架构师) | outline, planning | Chapter-by-chapter outline and plot planning |
| DraftAgent (专业写手) | writing, draft | Generate full chapter content with streaming |
| EditAgent (文风精修师) | editing, review | Polish, refine, and consistency review |
| ReviewAgent | review, analysis | Quality scoring and consistency check |
| WorldAgent (世界观构建师) | world_building, setting | Geography, magic system, social structure |
| CharacterAgent (角色塑造师) | character_design, development | Personality, background, goals, arcs |
| StyleAgent (开篇钩子师) | hook, opening | Opening hook design (first 3 chapters) |
| PlotAgent | plot, structure | Plot analysis and progression suggestions |

### NovelOrchestrator (State Machine)
Manages the full novel creation pipeline through sequential stages:
`planning → worldbuilding → characters → style → outlining → drafting → editing → review → done`

Supports pause/resume, real-time SSE streaming to frontend, and consistency checking between stages.

### Chapter Writing Loop (SKELETON → DETAIL → POLISH)
Each chapter goes through a 3-phase writing loop:
- **SKELETON（骨架）**: 故事架构师 + 世界观构建师 + 角色塑造师 → chapter outline & key events
- **DETAIL（血肉）**: 专业写手 → streaming full chapter content generation
- **POLISH（打磨）**: 文风精修师 → consistency review & polish (every 5 chapters or deep mode)

### 3-Layer Memory System
- **Working memory**: Last 3 chapters complete content
- **Short-term memory**: Chapter summaries with index numbers
- **Long-term memory**: Characters, world rules, unresolved foreshadowing
- Dynamic importance scoring: `base_score * (1 + log(refs+1)) * time_decay`

### Learning Engine
Tracks user style edits, builds word preferences, maintains anti-AI-patterns list. Applied automatically during draft generation.

### LLM Client Abstraction
Supports 10+ providers with hot-swappable configuration. Current provider stored in `.env` and `LLMConfigDB`.

## Common Commands

### Backend
```bash
# Install Python dependencies (from project root)
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"

# Start backend (auto-copies .env.example → .env if missing)
python run.py

# Or directly with uvicorn (run.py 使用 8080，保持一致)
python -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8080

# Run comprehensive tests
python test_project.py

# Check database integrity
python check_db.py
```

### Frontend
```bash
# Install dependencies
npm install

# Start dev server (port 8080)
npm run dev

# Build production bundle (outputs to dist/)
npm run build

# Preview production build
npm run preview
```

### Both (manually)
```bash
# Terminal 1: Start backend
python run.py

# Terminal 2: Start frontend
npm run dev

# Or use concurrently (install globally: npm install -g concurrently)
concurrently "python run.py" "npm run dev"
```

### Access Points
- Frontend: http://localhost:8080
- Backend API: http://localhost:8080
- API docs (Swagger): http://localhost:8080/docs

## Key Patterns to Follow

### Adding a New Skill
1. Create `src/backend/agents/<name>_agent.py` inheriting from `BaseAgent`
2. Implement `async process(context: Dict[str, Any]) -> Any`
3. Register in `AgentRegistryInitializer._initialize_agents()`
4. Add endpoints in `src/backend/main.py`
5. Add UI components in `src/frontend/src/components/`

### Adding API Endpoints
Endpoints go in `src/backend/main.py` under the `app` FastAPI instance. The backend is a monolith — routes are defined directly in main.py rather than separate router files.

### Memory Management
When modifying the memory system, respect the token budget: `max_context_tokens = model_context_size * 0.6` (default 76,800 tokens from 128K). Priority order: CRITICAL > HIGH > MEDIUM > LOW.

### Database Changes
SQLAlchemy models in `src/backend/db/models.py` → CRUD operations in `src/backend/db/crud.py` → Pydantic schemas in `src/backend/models/schemas.py`. Frontend types in `src/frontend/src/types.ts` mirror the backend schemas.

### LLM Provider Changes
Configure via the frontend LLMConfigPanel or direct API calls. Configuration is stored in `LLMConfigDB` and can be hot-swapped at runtime.

## Test Suite

The test script (`test_project.py`) covers 7 modules with 111 test assertions:
1. Agent registration system (10 tests)
2. Memory system (8 tests)
3. Learning engine (7 tests)
4. All 6 skill implementations (16 tests)
5. Agent registry initializer (10 tests)
6. Pydantic schemas (52 tests)
7. FastAPI main app (8 tests)

Run with: `python test_project.py`

## Important Notes

- No CI/CD pipelines exist yet; no Jest or pytest configuration — `test_project.py` is the sole test runner
- TypeScript is strict mode with `noUnusedLocals` and `noUnusedParameters` enabled
- The frontend has no UI framework — all styling is custom CSS Modules
- The backend uses a monolithic `main.py` for routes (not separate router files)
- SQLite database file: `novel_agent.db` (下划线，见 `.env` 的 DATABASE_URL 与 `db/database.py` 默认值)
- Windows requires `asyncio.WindowsSelectorEventLoopPolicy()` set before other imports
- SSE streaming is used for real-time orchestrator progress updates
- The `.env` file is auto-generated from `.env.example` on first run via `run.py`
