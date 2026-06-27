import React, { useState, useEffect } from "react";
import { api } from "../api";

// ──────────── CSS-in-JS styles ────────────
const S: Record<string, React.CSSProperties> = {
  layout: { display: "flex", gap: 16, height: "calc(100vh - 160px)", minHeight: 600 },
  left: {
    width: 380, minWidth: 320, flexShrink: 0,
    background: "#fff", borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,.06)",
    display: "flex", flexDirection: "column", overflow: "hidden",
  },
  right: {
    flex: 1, background: "#fff", borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,.06)",
    overflow: "hidden", display: "flex", flexDirection: "column",
  },
  leftHeader: {
    padding: "16px 20px",
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", color: "#fff",
  },
  leftBody: { padding: 20, flex: 1, overflowY: "auto" },
  label: { fontSize: 12, color: "#6b7280", marginBottom: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 },
  input: {
    width: "100%", padding: "8px 12px", border: "1px solid #e5e7eb", borderRadius: 8,
    fontSize: 14, outline: "none", boxSizing: "border-box", marginBottom: 12,
  },
  select: {
    width: "100%", padding: "8px 12px", border: "1px solid #e5e7eb", borderRadius: 8,
    fontSize: 14, outline: "none", boxSizing: "border-box", marginBottom: 12, background: "#fff",
  },
  btnPrimary: {
    width: "100%", padding: "12px 0", background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 15,
    fontWeight: 700, marginTop: 8, transition: "opacity .2s",
  },
  btnSecondary: {
    padding: "8px 16px", background: "#f3f4f6", color: "#374151", border: "none",
    borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 600,
  },
  rightHeader: {
    padding: "14px 20px", borderBottom: "1px solid #f0f0f0", display: "flex",
    alignItems: "center", justifyContent: "space-between", flexShrink: 0,
  },
  rightBody: { padding: 24, flex: 1, overflowY: "auto" },
  sectionTitle: {
    fontSize: 16, fontWeight: 700, color: "#1f2937", marginTop: 20, marginBottom: 12,
    paddingBottom: 6, borderBottom: "2px solid #667eea", display: "inline-block",
  },
  card: {
    background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 10,
    padding: 16, marginBottom: 12,
  },
  chip: {
    display: "inline-block", padding: "4px 12px", borderRadius: 999,
    background: "#e0e7ff", color: "#3730a3", fontSize: 12, fontWeight: 600, margin: "2px 4px 2px 0",
  },
  chapterTitle: { fontSize: 14, fontWeight: 700, color: "#1f2937", marginBottom: 6 },
  chapterSummary: { fontSize: 13, color: "#6b7280", lineHeight: 1.6 },
  prose: {
    fontSize: 15, lineHeight: 1.9, color: "#374151", whiteSpace: "pre-wrap",
    background: "#fafafa", padding: 24, borderRadius: 8, border: "1px solid #e5e7eb",
    marginBottom: 16,
  },
  emptyState: {
    textAlign: "center", padding: "60px 20px", color: "#9ca3af",
  },
  loadingBar: {
    height: 4, width: 120, borderRadius: 2,
    background: "linear-gradient(90deg, #667eea, #764ba2, #667eea)",
    backgroundSize: "200% 100%",
  },
};

// ──────────── 解析后端返回的数据 ────────────
// 后端返回: { success, novel_id, result: { success, results: { worldbuilding, characters, outlining, drafting, ... }, state } }

function getResults(data: any) {
  if (!data) return null;
  // 可能是 result.result 或 data.result
  const r = data.result || data;
  return r.results || r.result || null;
}

function RenderWorldbuilding({ results }: { results: any }) {
  const w = results?.worldbuilding;
  if (!w) return null;
  return (
    <div>
      <div style={S.sectionTitle}>🌍 世界观</div>
      <div style={S.card}>
        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>{w.name || "未命名"}</div>
        <div style={{ fontSize: 12, color: "#667eea", marginBottom: 8 }}>{w.category || ""}</div>
        {w.description && <div style={{ fontSize: 14, color: "#374151", lineHeight: 1.6 }}>{w.description}</div>}
      </div>
      {w.rules?.length > 0 && (
        <div style={S.card}>
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>规则</div>
          {w.rules.map((r: string, i: number) => (
            <div key={i} style={{ fontSize: 13, color: "#4b5563", padding: "4px 0", paddingLeft: 12, borderLeft: "3px solid #e0e7ff" }}>
              {r}
            </div>
          ))}
        </div>
      )}
      {w.locations?.length > 0 && (
        <div style={S.card}>
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>地点</div>
          <div>{w.locations.map((l: string, i: number) => <span key={i} style={S.chip}>{l}</span>)}</div>
        </div>
      )}
      {w.factions?.length > 0 && (
        <div style={S.card}>
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>势力</div>
          <div>{w.factions.map((f: string, i: number) => <span key={i} style={S.chip}>{f}</span>)}</div>
        </div>
      )}
    </div>
  );
}

function RenderCharacters({ results }: { results: any }) {
  const chars = results?.characters;
  if (!chars) return null;
  const list = (Array.isArray(chars) ? chars : [chars]).filter(Boolean);
  if (list.length === 0) return null;
  return (
    <div>
      <div style={S.sectionTitle}>👥 角色</div>
      {list.map((c: any, i: number) => (
        <div key={i} style={S.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontWeight: 700, fontSize: 15 }}>{c.name || "未命名"}</span>
            <span style={{
              ...S.chip,
              background: c.role === "protagonist" ? "#d1fae5" : "#e0e7ff",
              color: c.role === "protagonist" ? "#065f46" : "#3730a3",
            }}>
              {c.role === "protagonist" ? "主角" : c.role === "antagonist" ? "反派" : "配角"}
            </span>
          </div>
          {c.background && <div style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.5 }}>{c.background}</div>}
          {c.personality && <div style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>性格：{c.personality}</div>}
          {c.aliases?.length > 0 && <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>别名：{c.aliases.join("、")}</div>}
        </div>
      ))}
    </div>
  );
}

function RenderOutline({ results }: { results: any }) {
  const o = results?.outlining;
  if (!o) return null;
  const chapters = o.chapters || o;
  const summary = o.summary || "";
  return (
    <div>
      <div style={S.sectionTitle}>📋 大纲</div>
      {summary && <div style={{ fontSize: 14, color: "#374151", marginBottom: 16, lineHeight: 1.6 }}>{summary}</div>}
      {Array.isArray(chapters) && chapters.map((ch: any, i: number) => (
        <div key={i} style={S.card}>
          <div style={S.chapterTitle}>第{i + 1}章 {ch.title || ch.name || ""}</div>
          <div style={S.chapterSummary}>{ch.summary || ch.description || ""}</div>
        </div>
      ))}
    </div>
  );
}

function RenderDrafts({ results }: { results: any }) {
  const d = results?.drafting;
  if (!d) return null;
  const chapters = d.chapters || [];
  if (!chapters.length) return <div style={{ color: "#9ca3af", fontSize: 13 }}>暂无草稿</div>;
  return (
    <div>
      <div style={S.sectionTitle}> 正文草稿</div>
      {chapters.map((ch: any, i: number) => (
        <div key={i}>
          <div style={S.chapterTitle}>{ch.title}</div>
          <div style={S.prose}>{ch.content || "（无内容）"}</div>
        </div>
      ))}
    </div>
  );
}

function RenderReviews({ results }: { results: any }) {
  const r = results?.review;
  if (!r) return null;
  const reviews = r.reviews || [];
  if (!reviews.length) return <div style={{ color: "#9ca3af", fontSize: 13 }}>暂无审查</div>;
  return (
    <div>
      <div style={S.sectionTitle}>🔍 审查意见</div>
      {reviews.map((rv: any, i: number) => (
        <div key={i} style={S.card}>
          <div style={S.chapterTitle}>{rv.title}</div>
          <pre style={{ fontSize: 12, color: "#4b5563", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
            {JSON.stringify(rv.review, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}

// ─────────── Main Component ────────────

export const OrchestratorPanel: React.FC = () => {
  const [title, setTitle] = useState("青云界传说");
  const [theme, setTheme] = useState("穿越异世修真");
  const [tone, setTone] = useState("史诗");
  const [chapterCount, setChapterCount] = useState(5);
  const [running, setRunning] = useState(false);
  const [paused, setPaused] = useState(false);
  const [novelId, setNovelId] = useState("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState<string>("");
  // 预设选择
  const [presetCharacterId, setPresetCharacterId] = useState("");
  const [presetWorldId, setPresetWorldId] = useState("");
  const [presetCharacters, setPresetCharacters] = useState<any[]>([]);
  const [presetWorlds, setPresetWorlds] = useState<any[]>([]);
  // SSE 实时状态
  const [progress, setProgress] = useState<{stage?: string; chapter?: number; total?: number; message?: string}>({});
  const [liveChapters, setLiveChapters] = useState<any[]>([]);
  const [liveOutline, setLiveOutline] = useState<any[]>([]);
  const [liveWorld, setLiveWorld] = useState<any>(null);
  const [liveCharacters, setLiveCharacters] = useState<any[]>([]);
  // 流式内容
  const [streamingChapterIdx, setStreamingChapterIdx] = useState(-1);
  const [streamingText, setStreamingText] = useState("");
  const [livePipelineSteps, setLivePipelineSteps] = useState<any[]>([]);

  // 加载预设列表
  useEffect(() => {
    api.getPresets().then((data) => {
      if (data) {
        setPresetCharacters(data.characters || []);
        setPresetWorlds(data.world_settings || []);
      }
    }).catch(() => {});
  }, []);

  const start = async () => {
    console.log("[Orchestrator] start() called with:", { title, theme, tone, chapterCount, presetCharacterId, presetWorldId });
    setRunning(true);
    setError("");
    setResult(null);
    setActiveSection("");
    setProgress({});
    setLiveChapters([]);
    setLiveOutline([]);
    setLiveWorld(null);
    setLiveCharacters([]);
    setStreamingChapterIdx(-1);
    setStreamingText("");
    setPaused(false);
    setNovelId("");

    const es = api.orchestratorStream(
      title, theme, tone, chapterCount,
      presetCharacterId || undefined,
      presetWorldId || undefined,
    );
    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("[SSE] event:", data.event, data);

        switch (data.event) {
          case "run_all_start":
            setProgress({ stage: "开始生成", message: `《${data.title}》共${data.chapter_count}章` });
            setNovelId(data.novel_id || "");
            break;
          case "stage_start":
            setProgress({ stage: data.stage, message: `正在生成: ${data.stage}` });
            break;
          case "worldbuilding":
            setLiveWorld(data.data);
            setActiveSection("worldbuilding");
            break;
          case "characters":
            setLiveCharacters(data.data);
            setActiveSection("characters");
            break;
          case "outlining":
            setLiveOutline(data.data);
            setActiveSection("outlining");
            break;
          case "drafting_start":
            setProgress({ stage: "drafting", total: data.total, message: `开始8-Agent协作管道，共${data.total}章` });
            setLivePipelineSteps(data.pipeline_steps || []);
            break;
          case "pipeline_start":
            setProgress({ stage: "drafting", chapter: data.index, total: data.total, message: `第${data.index}章 管道启动` });
            setStreamingChapterIdx(data.index);
            setStreamingText("");
            setActiveSection("drafting");
            break;
          case "pipeline_phase":
            setProgress({ stage: "drafting", chapter: data.index, message: `第${data.index}章 ${data.phase_name || data.phase}` });
            break;
          case "pipeline_step":
            setProgress({ stage: "drafting", chapter: data.index, message: `第${data.index}章 ${data.name}: ${data.passed !== false ? "完成" : "需调整"}${data.word_count ? ` (${data.word_count}字)` : ""}` });
            break;
          case "pipeline_revision":
            setProgress({ stage: "drafting", chapter: data.index, message: `第${data.index}章 第${data.round}轮修订 (${data.score}分)` });
            break;
          case "pipeline_done":
            setProgress({ stage: "drafting", chapter: data.index, message: `第${data.index}章 管道完成${data.is_review_chapter ? " (已审查)" : ""} (${data.score}分/${data.word_count}字)` });
            break;
          case "chapter_start":
            setProgress({ stage: "drafting", chapter: data.index, total: data.total, message: `正在生成第${data.index}章: ${data.title}${data.is_review_chapter ? " 🔍审查章节" : ""}` });
            setStreamingChapterIdx(data.index);
            setStreamingText("");
            setActiveSection("drafting");
            break;
          case "chapter_token":
            // 流式 token：实时展示 AI 写作过程
            setStreamingChapterIdx(data.index);
            setStreamingText(data.partial || "");
            break;
          case "chapter_done":
            setLiveChapters((prev) => [...prev, data.chapter]);
            setProgress({ stage: "drafting", chapter: data.index, total: data.total, message: `第${data.index}章完成` });
            setStreamingChapterIdx(-1);
            setStreamingText("");
            setActiveSection("drafting");
            break;
          case "drafting_done":
            setProgress({ stage: "drafting", message: `全部${data.total}章正文完成` });
            break;
          case "run_all_done":
            setProgress({ stage: "done", message: "生成完成！等待保存结果…" });
            setPaused(false);
            // 不在此关闭连接：后端随后还会推送 save_success / final_result
            break;
          case "final_result":
            setResult(data.result);
            setRunning(false);
            setPaused(false);
            es.close();
            break;
          case "error":
            setError(data.error || "生成出错");
            setRunning(false);
            setPaused(false);
            es.close();
            break;
          case "stage_error":
            console.warn("[SSE] stage error:", data.stage, data.error);
            break;
        }
      } catch (e) {
        console.error("[SSE] parse error:", e, event.data);
      }
    };

    es.onerror = (err) => {
      // 区分正常关闭和真实错误：readyState=CLOSED(2) 表示连接正常关闭
      if (es.readyState === EventSource.CLOSED) {
        console.log("[SSE] connection closed normally");
        return;
      }
      console.error("[SSE] connection error:", err);
      setError("SSE连接出错，请检查网络或刷新页面重试");
      setRunning(false);
      setPaused(false);
      es.close();
    };
  };

  // 暂停/恢复
  const handlePause = async () => {
    if (!novelId) return;
    try {
      await fetch(`/api/orchestrator/${novelId}/pause`, { method: "POST" });
      setPaused(true);
      setProgress((prev) => ({ ...prev, message: "⏸️ 已暂停" }));
    } catch (e: any) {
      console.error("暂停失败:", e);
    }
  };

  const handleResume = async () => {
    if (!novelId) return;
    try {
      await fetch(`/api/orchestrator/${novelId}/resume`, { method: "POST" });
      setPaused(false);
      setProgress((prev) => ({ ...prev, message: "▶️ 已恢复" }));
    } catch (e: any) {
      console.error("恢复失败:", e);
    }
  };

  // 根据返回数据确定可用 section
  const sections = (() => {
    const res = getResults(result);
    if (!res) return [];
    const keys: string[] = [];
    if (res.worldbuilding) keys.push("worldbuilding");
    if (res.characters) keys.push("characters");
    if (res.outlining) keys.push("outlining");
    if (res.drafting) keys.push("drafting");
    if (res.review) keys.push("review");
    if (!keys.length) keys.push("raw");
    return keys;
  })();

  useEffect(() => {
    if (sections.length && !sections.includes(activeSection)) {
      setActiveSection(sections[0]);
    }
  }, [sections]);

  const sectionLabels: Record<string, string> = {
    worldbuilding: "🌍 世界观",
    characters: "👥 角色",
    outlining: "📋 大纲",
    drafting: " 正文",
    review: " 审查",
    raw: "📄 原始数据",
  };

  const res = getResults(result);

  return (
    <>
      <style>{`
        @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        * { box-sizing: border-box; }
      `}</style>

      <div style={S.layout}>
        {/* ─── 左栏：参数配置 ── */}
        <div style={S.left}>
          <div style={S.leftHeader}>
            <div style={{ fontSize: 16, fontWeight: 800, marginBottom: 2 }}> 全流程创作</div>
            <div style={{ fontSize: 12, opacity: 0.85 }}>大纲 → 世界观 → 角色 → 草稿</div>
          </div>
          <div style={S.leftBody}>
            <div style={S.label}>小说标题</div>
            <input style={S.input} value={title} onChange={(e) => setTitle(e.target.value)} />

            <div style={S.label}>主题</div>
            <input style={S.input} value={theme} onChange={(e) => setTheme(e.target.value)} />

            <div style={S.label}>文风</div>
            <select style={S.select} value={tone} onChange={(e) => setTone(e.target.value)}>
              <option value="史诗">史诗</option>
              <option value="冷峻">冷峻克制</option>
              <option value="诗意">诗意</option>
              <option value="写实">写实</option>
            </select>

            <div style={S.label}>章节数</div>
            <input style={S.input} type="number" min={1} max={2000} value={chapterCount}
                   onChange={(e) => setChapterCount(parseInt(e.target.value) || 5)} />

            {/* 预设角色选择 */}
            <div style={{ ...S.label, marginTop: 4 }}>预设角色 <span style={{ fontWeight: 400, color: "#9ca3af", fontSize: 11 }}>(可选)</span></div>
            <select style={S.select} value={presetCharacterId}
                    onChange={(e) => setPresetCharacterId(e.target.value)}>
              <option value="">-- 让AI自动生成 --</option>
              {presetCharacters.map((c: any) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.role === "protagonist" ? "主角" : c.role || "未知"}) - {c.novel_title}
                </option>
              ))}
            </select>

            {/* 预设世界观选择 */}
            <div style={{ ...S.label, marginTop: 4 }}>预设世界观 <span style={{ fontWeight: 400, color: "#9ca3af", fontSize: 11 }}>(可选)</span></div>
            <select style={S.select} value={presetWorldId}
                    onChange={(e) => setPresetWorldId(e.target.value)}>
              <option value="">-- 让AI自动生成 --</option>
              {presetWorlds.map((w: any) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.category || "未分类"}) - {w.novel_title}
                </option>
              ))}
            </select>

            <button style={{ ...S.btnPrimary, opacity: running ? 0.6 : 1 }} disabled={running} onClick={start}>
              {running ? "⏳ 生成中…" : " 开始创作"}
            </button>

            {/* 暂停/恢复按钮 */}
            {running && (
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                {!paused ? (
                  <button style={{
                    padding: "12px 0", background: "#ef4444", color: "#fff", border: "none",
                    borderRadius: 8, fontWeight: 700, cursor: "pointer", fontSize: 15, flex: 1,
                  }} onClick={handlePause}>
                    ⏸️ 暂停
                  </button>
                ) : (
                  <button style={{ ...S.btnPrimary, flex: 1 }} onClick={handleResume}>
                    ▶️ 继续
                  </button>
                )}
              </div>
            )}

            {error && (
              <div style={{ marginTop: 16, padding: 12, background: "#fef2f2", borderRadius: 8, color: "#dc2626", fontSize: 13 }}>
                ❌ {error}
              </div>
            )}

            {/* 实时进度显示 */}
            {running && progress.message && (
              <div style={{ marginTop: 16, padding: 12, background: "#f0fdf4", borderRadius: 8, border: "1px solid #bbf7d0" }}>
                <div style={{ fontSize: 12, color: "#15803d", fontWeight: 600, marginBottom: 4 }}>
                  {progress.stage === "drafting" && progress.total
                    ? `📝 正文进度: ${progress.chapter || 0}/${progress.total}章`
                    : progress.stage === "done"
                    ? "✅ 完成"
                    : `🔄 ${progress.message}`}
                </div>
                {progress.stage === "drafting" && progress.total && (
                  <div style={{ height: 6, background: "#e5e7eb", borderRadius: 3, overflow: "hidden", marginTop: 6 }}>
                    <div style={{
                      height: "100%",
                      width: `${((progress.chapter || 0) / progress.total) * 100}%`,
                      background: "linear-gradient(90deg, #667eea, #764ba2)",
                      borderRadius: 3,
                      transition: "width 0.3s ease",
                    }} />
                  </div>
                )}
              </div>
            )}

            {/* 完成后的 section 切换按钮 */}
            {(sections.length > 0 || liveWorld || liveCharacters.length > 0 || liveOutline.length > 0 || liveChapters.length > 0) && (
              <div style={{ marginTop: 20, borderTop: "1px solid #f0f0f0", paddingTop: 16 }}>
                <div style={{ ...S.label, marginBottom: 8 }}>查看内容</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {liveWorld && (
                    <button style={{ ...S.btnSecondary, ...(activeSection === "worldbuilding" ? { background: "#667eea", color: "#fff" } : {}) }} onClick={() => setActiveSection("worldbuilding")}>
                      🌍 世界观
                    </button>
                  )}
                  {liveCharacters.length > 0 && (
                    <button style={{ ...S.btnSecondary, ...(activeSection === "characters" ? { background: "#667eea", color: "#fff" } : {}) }} onClick={() => setActiveSection("characters")}>
                      👥 角色
                    </button>
                  )}
                  {liveOutline.length > 0 && (
                    <button style={{ ...S.btnSecondary, ...(activeSection === "outlining" ? { background: "#667eea", color: "#fff" } : {}) }} onClick={() => setActiveSection("outlining")}>
                      📋 大纲
                    </button>
                  )}
                  {liveChapters.length > 0 && (
                    <button style={{ ...S.btnSecondary, ...(activeSection === "drafting" ? { background: "#667eea", color: "#fff" } : {}) }} onClick={() => setActiveSection("drafting")}>
                      📝 正文 ({liveChapters.length})
                    </button>
                  )}
                  {sections.map((s) => (
                    <button
                      key={s}
                      style={{
                        ...S.btnSecondary,
                        ...(activeSection === s ? { background: "#667eea", color: "#fff" } : {}),
                      }}
                      onClick={() => setActiveSection(s)}
                    >
                      {sectionLabels[s] || s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ─── 右栏：内容展示 ─── */}
        <div style={S.right}>
          <div style={S.rightHeader}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#1f2937" }}>
              {activeSection ? sectionLabels[activeSection] || activeSection : "创作工作台"}
            </div>
            {running && <div style={S.loadingBar} />}
          </div>

          <div style={S.rightBody}>
            {!result && !running && !error && !liveWorld && !liveCharacters.length && !liveOutline.length && !liveChapters.length && (
              <div style={S.emptyState}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>📖</div>
                <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>等待创作</div>
                <div style={{ fontSize: 13 }}>在左侧配置参数，点击「开始创作」生成小说内容</div>
              </div>
            )}

            {running && !liveWorld && !liveCharacters.length && !liveOutline.length && !liveChapters.length && (
              <div style={S.emptyState}>
                <div style={{ fontSize: 48, marginBottom: 12, animation: "shimmer 2s infinite" }}>⏳</div>
                <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>AI 创作中…</div>
                <div style={{ fontSize: 13, color: "#6b7280" }}>正在生成世界观、角色、大纲和正文</div>
              </div>
            )}

            {/* 根据选中 section 渲染对应内容 - 优先使用实时数据 */}
            {activeSection === "worldbuilding" && (
              liveWorld ? <RenderWorldbuilding results={{ worldbuilding: liveWorld }} /> : <RenderWorldbuilding results={res} />
            )}
            {activeSection === "characters" && (
              liveCharacters.length > 0 ? <RenderCharacters results={{ characters: liveCharacters }} /> : <RenderCharacters results={res} />
            )}
            {activeSection === "outlining" && (
              liveOutline.length > 0 ? <RenderOutline results={{ outlining: { chapters: liveOutline } }} /> : <RenderOutline results={res} />
            )}
            {activeSection === "drafting" && (
              <>
                {/* 8-Agent 协同写作进度 */}
                {livePipelineSteps.length > 0 && (
                  <div style={{
                    background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 8,
                    padding: 12, marginBottom: 16,
                  }}>
                    <div style={{ fontSize: 12, color: "#166534", fontWeight: 600, marginBottom: 8 }}>
                      ✍️ 8-Agent 协同写作
                    </div>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {livePipelineSteps.map((step: any, i: number) => (
                        <span key={i} style={{
                          padding: "2px 8px", borderRadius: 999, fontSize: 11,
                          background: step === "大纲规划师" ? "#dbeafe" :
                                       step === "世界观助理" ? "#e0e7ff" :
                                       step === "角色设计师" ? "#fce7f3" :
                                       step === "情节架构师" ? "#fef3c7" :
                                       step === "风格润色师" ? "#e0f2fe" :
                                       step === "正文作者" ? "#dcfce7" :
                                       step === "编辑润色" ? "#f3e8ff" :
                                       step === "质量审查" ? "#fee2e2" : "#f3f4f6",
                          color: step === "大纲规划师" ? "#1e40af" :
                                  step === "世界观助理" ? "#3730a3" :
                                  step === "角色设计师" ? "#9d174d" :
                                  step === "情节架构师" ? "#92400e" :
                                  step === "风格润色师" ? "#0c4a6e" :
                                  step === "正文作者" ? "#166534" :
                                  step === "编辑润色" ? "#6b21a8" :
                                  step === "质量审查" ? "#991b1b" : "#374151",
                          fontWeight: 600,
                          opacity: i <= 6 ? 1 : 0.7,
                        }}>
                          {step}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {/* 流式写作实时展示 */}
                {streamingChapterIdx > 0 && streamingText && (
                  <div style={{
                    background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 8,
                    padding: 16, marginBottom: 16,
                  }}>
                    <div style={{ fontSize: 12, color: "#92400e", fontWeight: 600, marginBottom: 8 }}>
                      ✍️ AI 正在写第{streamingChapterIdx}章（实时预览）…
                    </div>
                    <div style={{
                      fontSize: 15, lineHeight: 1.9, color: "#374151", whiteSpace: "pre-wrap",
                      maxHeight: 300, overflowY: "auto",
                    }}>
                      {streamingText}
                    </div>
                  </div>
                )}
                {liveChapters.length > 0 ? <RenderDrafts results={{ drafting: { chapters: liveChapters } }} /> : <RenderDrafts results={res} />}
              </>
            )}
            {activeSection === "review" && <RenderReviews results={res} />}
            {activeSection === "raw" && result && (
              <pre style={{ fontSize: 12, color: "#374151", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </div>
    </>
  );
};
