// 通过 Vite 反向代理访问后端，避免跨域和端口漂移。
// vite.config.ts 中已配置: '/api' -> 'http://127.0.0.1:8080'（与 run.py 端口一致）
// 如需直连后端，修改为 const API_BASE = "http://127.0.0.1:8080" 即可。
const API_BASE = "";

// ──────────── TypeScript 类型 ────────────

export interface Character {
  id?: string;
  name: string;
  role?: string;
  personality?: string;
  background?: string;
  goals?: string[];
  speech_pattern?: string;
  appearance?: string;
  aliases?: string[];
}

export interface WorldSetting {
  id?: string;
  name: string;
  description?: string;
  rules?: string[];
  key_locations?: string[];
  factions?: string[];
}

export interface NovelSummary {
  id: string;
  title: string;
  genre?: string;
  status?: string;
  current_word_count?: number;
  target_word_count?: number;
  updated_at?: string;
}

export interface Chapter {
  index: number;
  title: string;
  content?: string;
  word_count?: number;
  status?: string;
}

export interface LLMProvider {
  id: string;
  label: string;
  description: string;
  api_base?: string;
  models: string[];
  needs_api_key: boolean;
}

export interface LLMConfig {
  provider: string;
  api_key?: string;
  model?: string;
  api_base?: string;
}

// ──────────── 通用 HTTP 封装 ────────────

async function http(
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  body?: any,
  params?: Record<string, any>,
): Promise<any> {
  let url = `${API_BASE}${path}`;
  if (params && method === "GET") {
    const qs = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)]),
    ).toString();
    if (qs) url += `?${qs}`;
  }
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body !== undefined && method !== "GET" ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({ success: false, error: "解析失败" }));
  if (!res.ok) {
    const errMsg = data.detail || data.error || data.message || `HTTP ${res.status}`;
    throw new Error(errMsg);
  }
  return data;
}

// ──────────── 小说 / 章节 API ────────────

export const api = {
  // ── 通用 HTTP 方法（供 CRUD 组件使用）──
  get: (path: string, params?: Record<string, any>): Promise<any> =>
    http("GET", path, undefined, params),
  post: (path: string, body?: any): Promise<any> =>
    http("POST", path, body),
  put: (path: string, body?: any): Promise<any> =>
    http("PUT", path, body),
  delete: (path: string): Promise<any> =>
    http("DELETE", path),

  // 小说基础
  getNovels: (): Promise<{ novels: NovelSummary[] }> =>
    http("GET", "/api/novels").then((d) => d || { novels: [] }),
  createNovel: (title: string, genre: string): Promise<any> =>
    http("POST", "/api/novels", { title, genre }),

  // LLM Provider 配置（新）
  getLLMProviders: (): Promise<{ providers: LLMProvider[] }> =>
    http("GET", "/api/llm/providers"),
  getLLMConfig: (): Promise<LLMConfig & { provider_type: string; has_api_key: boolean }> =>
    http("GET", "/api/llm/config"),
  setLLMConfig: (cfg: LLMConfig): Promise<any> =>
    http("POST", "/api/llm/config", cfg),
  testLLM: (): Promise<any> => http("POST", "/api/llm/test"),
  fetchCustomModels: (provider: string, api_key: string, api_base: string): Promise<any> =>
    http("POST", "/api/llm/models", { provider, api_key, api_base }),

  // Agent 管理
  getAgents: (): Promise<any> => http("GET", "/api/agents"),

  // 创作端点
  createOutline: (theme: string, tone: string, chapter_count: number = 10): Promise<any> =>
    http("POST", "/api/create/outline", { theme, tone, chapter_count }),
  createDraft: (chapter_title: string, chapter_outline: string = ""): Promise<any> =>
    http("POST", "/api/create/draft", { chapter_title, chapter_outline }),
  createEdit: (content: string): Promise<any> =>
    http("POST", "/api/create/edit", { content }),
  createReview: (content: string): Promise<any> =>
    http("POST", "/api/create/review", { content }),
  createWorld: (theme: string): Promise<any> =>
    http("POST", "/api/create/world", { theme }),
  createCharacter: (role: string = "主角", world_info: string = ""): Promise<any> =>
    http("POST", "/api/create/character", { role, world_info }),
  createStyle: (preference: string = "冷峻克制", samples: string = ""): Promise<any> =>
    http("POST", "/api/create/style", { preference, samples }),
  analyzePlot: (summaries: string): Promise<any> =>
    http("POST", "/api/create/plot", { summaries }),

  // Orchestrator 全流程（新）
  orchestratorStart: (title: string, theme: string, tone: string = "史诗", chapter_count: number = 5): Promise<any> =>
    http("POST", "/api/orchestrator/start", { title, theme, tone, chapter_count }),
  orchestratorStream: (
    title: string,
    theme: string,
    tone: string = "史诗",
    chapter_count: number = 5,
    preset_character_id?: string,
    preset_world_id?: string,
  ): EventSource => {
    // SSE 端点是 GET 方式，通过 URL 参数传递
    const params = new URLSearchParams();
    params.append("title", title);
    params.append("theme", theme);
    params.append("tone", tone);
    params.append("chapter_count", String(chapter_count));
    if (preset_character_id) params.append("preset_character_id", preset_character_id);
    if (preset_world_id) params.append("preset_world_id", preset_world_id);
    return new EventSource(`${API_BASE}/api/orchestrator/stream?${params.toString()}`);
  },
  getPresets: (): Promise<{ characters: any[]; world_settings: any[] }> =>
    http("GET", "/api/presets"),
  orchestratorStage: (novel_id: string, stage: string): Promise<any> =>
    http("POST", "/api/orchestrator/stage", { novel_id, stage }),
  orchestratorStatus: (novel_id: string): Promise<any> =>
    http("GET", "/api/orchestrator/status", undefined, { novel_id }),
  orchestratorExport: (novel_id: string): Promise<any> =>
    http("GET", "/api/orchestrator/export", undefined, { novel_id }),
  orchestratorList: (): Promise<any> => http("GET", "/api/orchestrator/list"),

  // 记忆系统
  getMemoryStats: (novelId: string): Promise<any> =>
    http("GET", "/api/memory/stats", undefined, { novel_id: novelId }),
  storeCharacters: (characters: Character[]): Promise<any> =>
    http("POST", "/api/memory/characters", characters),
  storeWorldSettings: (settings: WorldSetting[]): Promise<any> =>
    http("POST", "/api/memory/world", settings),
  getMemoryContext: (novelId: string, chapterIdx: number): Promise<any> =>
    http("GET", "/api/memory/context", undefined, { novel_id: novelId, chapter_idx: chapterIdx }),
  searchMemory: (novelId: string, query: string, topK: number = 5): Promise<any> =>
    http("GET", "/api/memory/search", undefined, { novel_id: novelId, query, top_k: topK }),

  // 学习引擎
  getLearningStats: (): Promise<any> => http("GET", "/api/learning/stats"),
  getStyleFingerprint: (userId: string): Promise<any> =>
    http("GET", "/api/learning/fingerprint", undefined, { user_id: userId }),
  updateStyleFingerprint: (userId: string, data: any): Promise<any> =>
    http("POST", "/api/learning/fingerprint", { user_id: userId, ...data }),
  getLearningStatsByUser: (userId: string): Promise<any> =>
    http("GET", "/api/learning/stats", undefined, { user_id: userId }),
  submitFeedback: (feedback_type: string, before_text: string, after_text: string): Promise<any> =>
    http("POST", "/api/learning/feedback", { feedback_type, before_text, after_text }),

  // 执行日志
  executorStats: (): Promise<any> => http("GET", "/api/executor/stats"),
  executorRecent: (limit: number = 20): Promise<any> =>
    http("GET", "/api/executor/recent", undefined, { limit }),

  // 一致性检查
  checkConsistency: (novelId: string, chapterId: string): Promise<any> =>
    http("POST", "/api/consistency/check", { novel_id: novelId, chapter_id: chapterId }),

  // Prompt 管理
  listPrompts: (category?: string): Promise<any> =>
    http("GET", "/api/prompts/list", undefined, category ? { category } : undefined),
  createPrompt: (data: any): Promise<any> =>
    http("POST", "/api/prompts/create", data),
  updatePrompt: (id: string, data: any): Promise<any> =>
    http("PUT", `/api/prompts/${id}`, data),
  deletePrompt: (id: string): Promise<any> =>
    http("DELETE", `/api/prompts/${id}`),

  // 小说章节 CRUD
  getNovelDetail: (novelId: string): Promise<any> =>
    http("GET", `/api/novels/${novelId}`),
  updateNovel: (novelId: string, data: any): Promise<any> =>
    http("PUT", `/api/novels/${novelId}`, data),
  deleteNovel: (novelId: string): Promise<any> =>
    http("DELETE", `/api/novels/${novelId}`),
  getChapterDetail: (novelId: string, chapterId: string): Promise<any> =>
    http("GET", `/api/novels/${novelId}/chapters/${chapterId}`),
  updateChapter: (novelId: string, chapterId: string, data: any): Promise<any> =>
    http("PUT", `/api/novels/${novelId}/chapters/${chapterId}`, data),
  deleteChapter: (novelId: string, chapterId: string): Promise<any> =>
    http("DELETE", `/api/novels/${novelId}/chapters/${chapterId}`),
};
