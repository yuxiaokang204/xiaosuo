/**
 * OrchestratorPage — 全流程编排页
 * 左右布局：左侧配置面板 + 右侧实时章节正文输出
 * 模块级 Store 保证切换菜单时持续输出不中断
 */
import React, { useState, useRef, useCallback, useEffect, useReducer } from "react";

// ──────── 类型定义 ────────

interface PresetCharacter {
  id: string; name: string; role: string; personality: string; novel_title: string;
}

interface PresetWorld {
  id: string; name: string; category: string; description: string; novel_title: string;
}

interface StoreState {
  isRunning: boolean;
  novelId: string;
  chapterTitle: string;
  chapterContent: string;
  currentChapter: number;
  totalChapters: number;
  currentStage: string;
  events: { type: string; message: string; chapter?: number }[];
  error: string | null;
}

// ──────── 模块级 Store（切换菜单不丢失状态）────────

const _store: StoreState = {
  isRunning: false,
  novelId: "",
  chapterTitle: "",
  chapterContent: "",
  currentChapter: 0,
  totalChapters: 0,
  currentStage: "",
  events: [],
  error: null,
};
let _es: EventSource | null = null;
const _listeners = new Set<() => void>();

function notify() {
  _listeners.forEach((fn) => fn());
}

function stopOrchestrator() {
  if (_store.novelId) {
    fetch(`/api/orchestrator/${_store.novelId}/pause`, { method: "POST" }).catch(() => {});
  }
  if (_es) {
    _es.close();
    _es = null;
  }
  _store.isRunning = false;
  notify();
}

function useOrchestratorStore(): StoreState {
  const [, forceUpdate] = useReducer((x) => x + 1, 0);
  useEffect(() => {
    const listener = () => forceUpdate();
    _listeners.add(listener);
    return () => { _listeners.delete(listener); };
  }, []);
  return _store;
}

// ──────── 组件 ────────

export const OrchestratorPage: React.FC = () => {
  const store = useOrchestratorStore();

  // 本地 UI 状态（配置参数，不需要跨菜单保持）
  const [title, setTitle] = useState("");
  const [theme, setTheme] = useState("穿越异世");
  const [tone, setTone] = useState("史诗");
  const [chapterCount, setChapterCount] = useState(5);
  const [showLog, setShowLog] = useState(false);
  const [skipEditingReview, setSkipEditingReview] = useState(true);
  const [savedNovelId, setSavedNovelId] = useState("");
  const [mode, setMode] = useState<"loop" | "linear">("loop");  // v4.0: 默认 Loop 模式

  // 预设选择
  const [presets, setPresets] = useState<{ characters: PresetCharacter[]; world_settings: PresetWorld[] }>({ characters: [], world_settings: [] });
  const [loadingPresets, setLoadingPresets] = useState(false);
  const [selectedCharId, setSelectedCharId] = useState("");
  const [selectedWorldId, setSelectedWorldId] = useState("");

  const contentEndRef = useRef<HTMLDivElement>(null);

  // 加载预设列表
  useEffect(() => {
    fetchPresets();
  }, []);

  // 自动滚动到最新内容
  useEffect(() => {
    if (store.chapterContent && contentEndRef.current) {
      contentEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [store.chapterContent]);

  // 组件卸载时不关闭 SSE（保持后台运行）
  useEffect(() => {
    return () => {
      // 不关闭 SSE，保持后台持续输出
    };
  }, []);

  const fetchPresets = useCallback(async () => {
    setLoadingPresets(true);
    try {
      const data = await fetch("/api/presets").then((r) => r.json()).catch(() => ({ characters: [], world_settings: [] }));
      setPresets(data);
    } catch {
      // 忽略
    } finally {
      setLoadingPresets(false);
    }
  }, []);

  const startGeneration = useCallback(async () => {
    if (!title.trim()) return;

    // P0: LLM 前置检查
    try {
      const healthData = await fetch("/api/health").then(r => r.json());
      if (healthData.llm_provider === "mock") {
        _store.error = "⚠️ 未配置 LLM 模型，请先前往 [LLM 配置] 页面设置 API Key 和模型";
        _store.isRunning = false;
        notify();
        return;
      }
    } catch {
      _store.error = "⚠️ 无法连接后端服务，请确认后端已启动";
      _store.isRunning = false;
      notify();
      return;
    }

    // 调度标题到 TopBar
    window.dispatchEvent(new CustomEvent("novel-title", { detail: { title: title.trim() } }));

    // 重置 store
    _store.isRunning = true;
    _store.novelId = "";
    _store.currentChapter = 0;
    _store.totalChapters = chapterCount;
    _store.currentStage = "";
    _store.chapterTitle = "";
    _store.chapterContent = "";
    _store.events = [];
    _store.error = null;
    notify();

    const params = new URLSearchParams({
      title: title.trim(), theme, tone, chapter_count: String(chapterCount),
    });
    if (selectedCharId) params.append("preset_character_id", selectedCharId);
    if (selectedWorldId) params.append("preset_world_id", selectedWorldId);
    if (skipEditingReview) params.append("skip_editing_review", "true");
    const streamEndpoint = mode === "loop" ? "/api/orchestrator/stream" : "/api/orchestrator/stream";
    const url = `${streamEndpoint}?${params.toString()}`;

    if (_es) _es.close();
    const es = new EventSource(url);
    _es = es;

    es.onopen = () => {
      _store.events = [..._store.events, { type: "system", message: "🚀 已开始全流程生成" }];
      notify();
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // 回退机制：当浏览器未正确解析 SSE event: 字段时，通过 data.event 分发事件
        switch (data.event) {
          case "chapter_start": {
            const titleText = data.title || `第${data.index}章`;
            _store.chapterTitle = titleText;
            _store.chapterContent = "";
            _store.currentChapter = data.index;
            _store.totalChapters = data.total || chapterCount;
            _store.events = [..._store.events, { type: "system", message: `📝 正在生成 ${titleText}...`, chapter: data.index }];
            notify();
            return;
          }
          case "chapter_token": {
            if (data.token) {
              _store.chapterContent += data.token;
            } else if (data.partial) {
              _store.chapterContent = data.partial;
            }
            if (data.index) _store.currentChapter = data.index;
            notify();
            return;
          }
          case "chapter_done": { notify(); return; }
          case "chapter_error": {
            _store.events = [..._store.events, {
              type: "error",
              message: `⚠️ 第${data.index}章生成失败，已写入占位内容`,
              chapter: data.index,
            }];
            notify();
            return;
          }
          case "stage_start": {
            _store.currentStage = data.stage || "";
            _store.events = [..._store.events, { type: "info", message: `▶ 开始阶段: ${data.stage}` }];
            notify();
            return;
          }
          case "stage_done": {
            _store.currentStage = "";
            notify();
            return;
          }
          case "stage_error": {
            _store.error = data.error || "阶段执行出错";
            notify();
            return;
          }
          case "run_all_start": {
            if (data.novel_id) _store.novelId = data.novel_id;
            _store.events = [..._store.events, { type: "system", message: "📋 开始全流程编排" }];
            notify();
            return;
          }
          case "run_all_done": {
            _store.isRunning = false;
            notify();
            es.close();
            _es = null;
            return;
          }
          case "save_success": {
            _store.events = [..._store.events, {
              type: "success",
              message: data.message || `✅ 已保存到数据库 (ID: ${data.novel_id})`,
            }];
            _store.isRunning = false;
            setSavedNovelId(data.novel_id || "");
            notify();
            es.close();
            _es = null;
            return;
          }
          case "final_result": {
            _store.isRunning = false;
            notify();
            es.close();
            _es = null;
            return;
          }
          case "loop_start": {
            const loopNames = ["SKELETON 骨架层", "DETAIL 细节层", "POLISH 精修层"];
            const loopName = loopNames[data.loop] || `循环 ${data.loop}`;
            _store.events = [..._store.events, {
              type: "info",
              message: `🔄 开始 ${loopName} (深度: ${data.depth_level ?? "?"})`,
            }];
            notify();
            return;
          }
          case "loop_done": {
            _store.events = [..._store.events, {
              type: "success",
              message: `✅ ${data.summary || "循环完成"}`,
            }];
            notify();
            return;
          }
          case "error": {
            _store.error = data.error || "未知错误";
            notify();
            return;
          }
        }
        if (data.error) { _store.error = data.error; notify(); }
      } catch { /* ignore */ }
    };

    // 工作流事件
    es.addEventListener("run_all_start", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        if (data.novel_id) _store.novelId = data.novel_id;
        _store.events = [..._store.events, { type: "system", message: "📋 开始全流程编排" }];
        notify();
      } catch { /* ignore */ }
    });
    es.addEventListener("run_all_done", (_e: any) => {
      _store.isRunning = false;
      notify();
      es.close();
      _es = null;
    });
    es.addEventListener("run_all_aborted", (_e: any) => {
      _store.error = "编排已中止";
      _store.isRunning = false;
      notify();
      es.close();
      _es = null;
    });

    // 阶段事件
    es.addEventListener("stage_start", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        _store.currentStage = data.stage || "";
        _store.events = [..._store.events, { type: "info", message: `▶ 开始阶段: ${data.stage}` }];
        notify();
      } catch { /* ignore */ }
    });
    es.addEventListener("stage_progress", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        _store.currentStage = data.stage || _store.currentStage;
        notify();
      } catch { /* ignore */ }
    });
    es.addEventListener("stage_error", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        _store.error = data.error || "阶段执行出错";
        notify();
      } catch {
        _store.error = "阶段错误";
        notify();
      }
    });

    // 起草事件
    es.addEventListener("drafting_start", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        _store.totalChapters = data.total || chapterCount;
        _store.events = [..._store.events, { type: "info", message: `✍️ 开始撰写 (共${data.total || chapterCount}章)` }];
        notify();
      } catch { /* ignore */ }
    });
    es.addEventListener("drafting_done", (_e: any) => {
      // 撰写完成，不输出日志，仅刷新状态
      notify();
    });

    es.addEventListener("save_success", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        _store.events = [..._store.events, {
          type: "success",
          message: data.message || `✅ 已保存到数据库 (ID: ${data.novel_id})`,
        }];
        _store.isRunning = false;
        setSavedNovelId(data.novel_id || "");
        notify();
        es.close();
        _es = null;
      } catch { /* ignore */ }
    });

    // 编辑事件
    es.addEventListener("editing_start", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        _store.events = [..._store.events, { type: "info", message: `📝 开始编辑 (共${data.total || 0}章)` }];
        notify();
      } catch { /* ignore */ }
    });
    es.addEventListener("editing_done", (_e: any) => {
      notify();
    });

    // 审查事件
    es.addEventListener("review_start", (_e: any) => {
      _store.events = [..._store.events, { type: "info", message: "🔍 开始审查" }];
      notify();
    });
    es.addEventListener("review_done", (_e: any) => {
      notify();
    });

    // 核心：章节事件
    es.addEventListener("chapter_start", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        const titleText = data.title || `第${data.index}章`;
        _store.chapterTitle = titleText;
        _store.chapterContent = "";
        _store.currentChapter = data.index;
        _store.totalChapters = data.total || chapterCount;
        _store.events = [..._store.events, { type: "system", message: `📝 正在生成 ${titleText}...`, chapter: data.index }];
        notify();
      } catch { /* ignore */ }
    });

    es.addEventListener("chapter_token", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        if (data.token) {
          _store.chapterContent += data.token;
        } else if (data.partial) {
          _store.chapterContent = data.partial;
        }
        if (data.index) _store.currentChapter = data.index;
        notify();
      } catch { /* ignore */ }
    });

    es.addEventListener("chapter_done", (_e: any) => {
      // 章节完成，不输出日志（避免冗余），仅刷新状态
      notify();
    });

    // 单章重试多次仍失败：在日志中显式提示，避免用户误以为内容正常生成
    es.addEventListener("chapter_error", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        _store.events = [..._store.events, {
          type: "error",
          message: `⚠️ 第${data.index}章生成失败，已写入占位内容`,
          chapter: data.index,
        }];
        notify();
      } catch { /* ignore */ }
    });

    es.addEventListener("final_result", (_e: any) => {
      _store.isRunning = false;
      notify();
      es.close();
      _es = null;
    });

    // v4.0: Loop 循环事件
    es.addEventListener("loop_start", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        const loopNames = ["SKELETON 骨架层", "DETAIL 细节层", "POLISH 精修层"];
        const loopName = loopNames[data.loop] || `循环 ${data.loop}`;
        _store.events = [..._store.events, {
          type: "info",
          message: `🔄 开始 ${loopName} (深度: ${data.depth_level ?? "?"})`,
        }];
        notify();
      } catch { /* ignore */ }
    });
    es.addEventListener("loop_done", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        _store.events = [..._store.events, {
          type: "success",
          message: `✅ ${data.summary || "循环完成"}`,
        }];
        notify();
      } catch { /* ignore */ }
    });

    es.addEventListener("error", (e: any) => {
      try {
        const data = JSON.parse(e.data);
        _store.error = data.error || "未知错误";
      } catch {
        _store.error = "未知错误";
      }
      notify();
    });

    es.onerror = () => {
      _store.isRunning = false;
      es.close();
      _es = null;
      notify();
    };
  }, [title, theme, tone, chapterCount, selectedCharId, selectedWorldId]);

  const charCount = presets?.characters?.length ?? 0;
const worldCount = presets?.world_settings?.length ?? 0;

  return (
    <div style={{ display: "flex", gap: 0, height: "calc(100vh - 104px)", overflow: "hidden" }}>
      {/* ═══════ 左侧配置面板 ═══════ */}
      <div style={{
        width: 360,
        minWidth: 360,
        borderRight: "1px solid var(--border)",
        background: "var(--bg-secondary)",
        overflowY: "auto",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: "var(--text-primary)" }}>
          🚀 创作配置
        </h2>

        {/* 创作参数 */}
        <div style={{
          background: "var(--bg-primary)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: 16,
        }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 12px 0", color: "var(--text-secondary)" }}>
            📝 创作参数
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>小说标题 *</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="输入小说标题"
                className="input"
                disabled={store.isRunning}
                style={{ width: "100%", boxSizing: "border-box" }}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>小说类型</label>
              <select value={theme} onChange={(e) => setTheme(e.target.value)} className="select" disabled={store.isRunning} style={{ width: "100%", boxSizing: "border-box" }}>
                <option value="">选择类型</option>
                <optgroup label="热门类型">
                  <option value="穿越异世">穿越异世</option>
                  <option value="重生复仇">重生复仇</option>
                  <option value="玄幻修仙">玄幻修仙</option>
                  <option value="都市修真">都市修真</option>
                  <option value="科幻末世">科幻末世</option>
                  <option value="悬疑灵异">悬疑灵异</option>
                  <option value="游戏竞技">游戏竞技</option>
                  <option value="历史架空">历史架空</option>
                </optgroup>
                <optgroup label="更多类型">
                  <option value="武侠江湖">武侠江湖</option>
                  <option value="现代言情">现代言情</option>
                  <option value="古代言情">古代言情</option>
                  <option value="盗墓探险">盗墓探险</option>
                  <option value="无限流">无限流</option>
                  <option value="系统流">系统流</option>
                  <option value="种田文">种田文</option>
                  <option value="综漫同人">综漫同人</option>
                </optgroup>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>风格基调</label>
              <select value={tone} onChange={(e) => setTone(e.target.value)} className="select" disabled={store.isRunning} style={{ width: "100%", boxSizing: "border-box" }}>
                <option value="">选择风格</option>
                <optgroup label="常用风格">
                  <option value="爽文">爽文（快节奏打脸）</option>
                  <option value="轻松搞笑">轻松搞笑</option>
                  <option value="史诗宏大">史诗宏大</option>
                  <option value="暗黑残酷">暗黑残酷</option>
                  <option value="热血战斗">热血战斗</option>
                  <option value="智斗谋略">智斗谋略</option>
                  <option value="悬疑烧脑">悬疑烧脑</option>
                  <option value="温馨治愈">温馨治愈</option>
                </optgroup>
                <optgroup label="更多风格">
                  <option value="快节奏">快节奏</option>
                  <option value="慢热细腻">慢热细腻</option>
                  <option value="冷峻写实">冷峻写实</option>
                  <option value="文艺抒情">文艺抒情</option>
                  <option value="幽默讽刺">幽默讽刺</option>
                  <option value="凄美虐心">凄美虐心</option>
                  <option value="日常温馨">日常温馨</option>
                  <option value="惊悚恐怖">惊悚恐怖</option>
                </optgroup>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>章节数</label>
              <input
                type="number"
                value={chapterCount}
                onChange={(e) => setChapterCount(Number(e.target.value))}
                min={1} max={50}
                className="input"
                disabled={store.isRunning}
                style={{ width: "100%", boxSizing: "border-box" }}
              />
            </div>
          </div>
        </div>

        {/* 预设资源 */}
        <div style={{
          background: "var(--bg-primary)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: 16,
        }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 12px 0", color: "var(--text-secondary)" }}>
            📌 预设资源（可选）
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>角色 ({charCount} 个)</label>
              {loadingPresets ? (
                <div className="skeleton" style={{ height: 36, borderRadius: 6 }} />
              ) : charCount === 0 ? (
                <div style={{ padding: 8, background: "var(--bg-tertiary)", borderRadius: 6, fontSize: 12, color: "var(--text-muted)", textAlign: "center" }}>
                  暂无角色预设
                </div>
              ) : (
                <select value={selectedCharId} onChange={(e) => setSelectedCharId(e.target.value)} className="select" disabled={store.isRunning} style={{ width: "100%", boxSizing: "border-box" }}>
                  <option value="">不选择角色</option>
                  {presets.characters.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}（{c.role}）</option>
                  ))}
                </select>
              )}
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>世界观 ({worldCount} 个)</label>
              {loadingPresets ? (
                <div className="skeleton" style={{ height: 36, borderRadius: 6 }} />
              ) : worldCount === 0 ? (
                <div style={{ padding: 8, background: "var(--bg-tertiary)", borderRadius: 6, fontSize: 12, color: "var(--text-muted)", textAlign: "center" }}>
                  暂无世界观预设
                </div>
              ) : (
                <select value={selectedWorldId} onChange={(e) => setSelectedWorldId(e.target.value)} className="select" disabled={store.isRunning} style={{ width: "100%", boxSizing: "border-box" }}>
                  <option value="">不选择世界观</option>
                  {presets.world_settings.map((w) => (
                    <option key={w.id} value={w.id}>{w.name}（{w.category}）</option>
                  ))}
                </select>
              )}
            </div>
          </div>
        </div>

        {/* 阶段选项 */}
        <div style={{
          background: "var(--bg-primary)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: 16,
        }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 12px 0", color: "var(--text-secondary)" }}>
            ⚙️ 生成选项
          </h3>
          {/* v4.0: 模式选择器 */}
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <button
              onClick={() => setMode("loop")}
              disabled={store.isRunning}
              className={mode === "loop" ? "btn btn-primary btn-sm" : "btn btn-ghost btn-sm"}
              style={{ flex: 1, fontSize: 12, fontWeight: mode === "loop" ? 600 : 400 }}
            >
              🔄 循环模式
            </button>
            <button
              onClick={() => setMode("linear")}
              disabled={store.isRunning}
              className={mode === "linear" ? "btn btn-primary btn-sm" : "btn btn-ghost btn-sm"}
              style={{ flex: 1, fontSize: 12, fontWeight: mode === "linear" ? 600 : 400 }}
            >
              📋 线性模式
            </button>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13 }}>
            <input
              type="checkbox"
              checked={skipEditingReview}
              onChange={(e) => setSkipEditingReview(e.target.checked)}
              disabled={store.isRunning}
            />
            <span>章节完成后跳过编辑和审查（立即保存）</span>
          </label>
        </div>

        {/* 开始 / 停止按钮 */}
        <div style={{ display: "flex", gap: 8 }}>
          {!store.isRunning ? (
            <button
              onClick={startGeneration}
              disabled={!title.trim()}
              className="btn btn-primary"
              style={{ flex: 1, padding: "12px 16px", fontSize: 15, fontWeight: 600 }}
            >
              🚀 开始全流程创作
            </button>
          ) : (
            <button
              onClick={stopOrchestrator}
              className="btn btn-danger"
              style={{ flex: 1, padding: "12px 16px", fontSize: 15, fontWeight: 600 }}
            >
              ⏹ 停止生成
            </button>
          )}
        </div>

        {/* 错误提示 */}
        {store.error && (
          <div style={{
            padding: 10, background: "var(--danger-light)",
            borderRadius: 8, color: "var(--danger)", fontSize: 13,
          }}>
            ❌ {store.error}
          </div>
        )}
      </div>

      {/* ═══════ 右侧输出面板 ═══════ */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: "var(--bg-primary)" }}>
        {/* 保存成功横幅 */}
        {savedNovelId && (
          <div style={{
            padding: "10px 24px",
            borderBottom: "1px solid var(--success)",
            background: "rgba(34, 197, 94, 0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}>
            <span style={{ fontSize: 13, color: "var(--success)", fontWeight: 600 }}>
              ✅ 小说已保存到数据库（ID: {savedNovelId}）
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => window.open(`/novel/${savedNovelId}`, "_blank")}
                className="btn btn-sm"
                style={{ background: "var(--success)", color: "#fff", border: "none" }}
              >
                📖 查看小说
              </button>
              <button
                onClick={() => setSavedNovelId("")}
                className="btn btn-ghost btn-sm"
                style={{ fontSize: 12 }}
              >
                关闭
              </button>
            </div>
          </div>
        )}

        {/* 状态栏 / 进度条 */}
        {(store.isRunning || store.currentStage) && (
          <div style={{
            padding: "12px 24px",
            borderBottom: "1px solid var(--border)",
            background: "var(--bg-secondary)",
            flexShrink: 0,
          }}>
            {/* 阶段指示器 */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              {store.isRunning && <span className="spinner spinner-sm" />}
              <span style={{ fontSize: 13, color: "var(--accent)", fontWeight: 600 }}>
                {store.currentStage ? `阶段: ${store.currentStage}` : "准备中..."}
              </span>
              {store.currentChapter > 0 && (
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                  第 {store.currentChapter}/{store.totalChapters} 章
                </span>
              )}
              {store.currentChapter === 0 && store.isRunning && (
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>正在生成世界观与角色设定...</span>
              )}
            </div>
            {/* 进度条 */}
            {store.isRunning && (
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{
                  flex: 1, height: 6, background: "var(--bg-tertiary)",
                  borderRadius: 3, overflow: "hidden",
                }}>
                  <div style={{
                    height: "100%",
                    width: store.currentChapter > 0
                      ? `${(store.currentChapter / store.totalChapters) * 100}%`
                      : "10%",
                    background: "linear-gradient(90deg, var(--accent), var(--info))",
                    transition: "width 500ms ease", borderRadius: 3,
                  }} />
                </div>
                <span style={{ fontSize: 11, color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                  {store.currentChapter > 0
                    ? `${Math.round((store.currentChapter / store.totalChapters) * 100)}%`
                    : "初始化..."}
                </span>
                <button onClick={() => setShowLog(!showLog)} className="btn btn-ghost btn-sm" style={{ fontSize: 11, whiteSpace: "nowrap" }}>
                  {showLog ? "隐藏日志" : "日志"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* 章节正文区域 */}
        <div style={{ flex: 1, overflowY: "auto", padding: "32px 48px" }}>
          {(store.chapterTitle || store.chapterContent) ? (
            <div style={{ maxWidth: 800, margin: "0 auto" }}>
              <h2 style={{
                textAlign: "center", fontSize: 22, fontWeight: 700,
                marginBottom: 24, paddingBottom: 16,
                borderBottom: "1px solid var(--border)", color: "var(--accent)",
              }}>
                {store.chapterTitle}
              </h2>
              <div style={{
                fontFamily: "'Noto Serif SC', Georgia, serif",
                fontSize: 16, lineHeight: 2.2,
                whiteSpace: "pre-wrap", color: "var(--text-primary)",
              }}>
                {store.chapterContent || (
                  <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>
                    正在生成章节内容...
                  </span>
                )}
              </div>
              <div ref={contentEndRef} />
            </div>
          ) : (
            <div style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", height: "100%",
              color: "var(--text-muted)",
            }}>
              <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>📖</div>
              <p style={{ fontSize: 15, margin: 0, fontWeight: 600 }}>开始创作你的第一部小说</p>
              <div style={{ marginTop: 20, textAlign: "left", fontSize: 13, opacity: 0.8, lineHeight: 2 }}>
                <div style={{ marginBottom: 4 }}>1. 输入小说标题、主题、风格</div>
                <div style={{ marginBottom: 4 }}>2. 可选：选择预设角色和世界观</div>
                <div style={{ marginBottom: 4 }}>3. 点击「开始全流程创作」启动 6 个 AI Skill 协同创作</div>
                <div style={{ marginBottom: 4 }}>4. 章节正文将在此处实时生成</div>
              </div>
            </div>
          )}
        </div>

        {/* 事件日志（可折叠） */}
        {showLog && (
          <div style={{
            borderTop: "1px solid var(--border)",
            background: "var(--bg-secondary)",
            flexShrink: 0,
            maxHeight: 200,
            overflowY: "auto",
          }}>
            <div style={{ padding: "8px 24px", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", borderBottom: "1px solid var(--border-subtle)" }}>
              📋 生成日志
            </div>
            <div style={{
              padding: "8px 24px",
              fontFamily: "monospace", fontSize: 12, lineHeight: 1.8,
            }}>
              {store.events.length === 0 ? (
                <span style={{ color: "var(--text-muted)" }}>等待开始...</span>
              ) : (
                store.events.map((ev, i) => (
                  <div key={i} style={{
                    padding: "1px 0",
                    color: ev.type === "error" ? "var(--danger)"
                      : ev.type === "success" ? "var(--success)"
                      : ev.type === "system" ? "var(--accent)"
                      : "var(--text-primary)",
                  }}>
                    {ev.message}
                    {ev.chapter && ` (第${ev.chapter}章)`}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};