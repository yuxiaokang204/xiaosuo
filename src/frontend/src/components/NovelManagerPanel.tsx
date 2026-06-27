import React, { useState, useEffect } from "react";

// ──────────── CSS-in-JS styles ────────────
const S: Record<string, React.CSSProperties> = {
  layout: { display: "flex", gap: 16, height: "calc(100vh - 200px)", minHeight: 500 },
  sidebar: {
    width: 300, minWidth: 260, flexShrink: 0,
    background: "#fff", borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,.06)",
    display: "flex", flexDirection: "column", overflow: "hidden",
  },
  sidebarHeader: {
    padding: "14px 18px",
    background: "linear-gradient(135deg, #10b981 0%, #059669 100%)", color: "#fff",
  },
  sidebarBody: { padding: 12, flex: 1, overflowY: "auto" },
  main: {
    flex: 1, background: "#fff", borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,.06)",
    overflow: "hidden", display: "flex", flexDirection: "column",
  },
  mainHeader: {
    padding: "14px 20px", borderBottom: "1px solid #f0f0f0", display: "flex",
    alignItems: "center", justifyContent: "space-between", flexShrink: 0,
  },
  mainBody: { padding: 24, flex: 1, overflowY: "auto" },
  novelCard: {
    padding: 12, borderRadius: 8, border: "1px solid #e5e7eb", marginBottom: 8,
    cursor: "pointer", transition: "all .15s",
  },
  novelCardActive: {
    padding: 12, borderRadius: 8, border: "2px solid #10b981", marginBottom: 8,
    cursor: "pointer", background: "#ecfdf5",
  },
  sectionTitle: {
    fontSize: 16, fontWeight: 700, color: "#1f2937", marginTop: 20, marginBottom: 12,
    paddingBottom: 6, borderBottom: "2px solid #10b981", display: "inline-block",
  },
  card: {
    background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 10,
    padding: 16, marginBottom: 12,
  },
  chip: {
    display: "inline-block", padding: "4px 12px", borderRadius: 999,
    background: "#d1fae5", color: "#065f46", fontSize: 12, fontWeight: 600, margin: "2px 4px 2px 0",
  },
  textarea: {
    width: "100%", minHeight: 200, padding: 12, border: "1px solid #e5e7eb", borderRadius: 8,
    fontSize: 14, lineHeight: 1.8, fontFamily: "inherit", resize: "vertical", boxSizing: "border-box",
  },
  btn: {
    padding: "8px 16px", background: "#10b981", color: "#fff", border: "none",
    borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 600, marginRight: 8,
  },
  btnSecondary: {
    padding: "8px 16px", background: "#f3f4f6", color: "#374151", border: "none",
    borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 600, marginRight: 8,
  },
  btnDanger: {
    padding: "8px 16px", background: "#fee2e2", color: "#dc2626", border: "none",
    borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 600, marginRight: 8,
  },
  emptyState: {
    textAlign: "center", padding: "60px 20px", color: "#9ca3af",
  },
  chapterTab: {
    padding: "6px 14px", border: "1px solid #e5e7eb", borderRadius: 6,
    cursor: "pointer", fontSize: 13, fontWeight: 600, marginRight: 6, marginBottom: 6,
    background: "#fff", color: "#374151",
  },
  chapterTabActive: {
    padding: "6px 14px", border: "2px solid #10b981", borderRadius: 6,
    cursor: "pointer", fontSize: 13, fontWeight: 600, marginRight: 6, marginBottom: 6,
    background: "#ecfdf5", color: "#065f46",
  },
  label: { fontSize: 12, color: "#6b7280", marginBottom: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 },
};

interface NovelSummary {
  id: string;
  title: string;
  genre?: string;
  status?: string;
  current_word_count?: number;
  target_word_count?: number;
  created_at?: string;
  updated_at?: string;
}

interface ChapterDetail {
  id: string;
  title: string;
  outline?: string;
  content?: string;
  word_count?: number;
  status?: string;
}

interface NovelDetail {
  novel: { id: string; title: string; genre: string; status: string; current_word_count: number };
  chapters: ChapterDetail[];
  characters: { name: string; role?: string; personality?: string; background?: string }[];
  world_settings: { name: string; category?: string; description?: string; rules?: string[] }[];
  style_guides: { tone?: string; pacing_preference?: string }[];
}

export const NovelManagerPanel: React.FC = () => {
  const [novels, setNovels] = useState<NovelSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [detail, setDetail] = useState<NovelDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeChapterIdx, setActiveChapterIdx] = useState(0);
  const [editingContent, setEditingContent] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [activeView, setActiveView] = useState<"chapters" | "characters" | "world" | "style">("chapters");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // 加载小说列表
  const loadNovels = async () => {
    try {
      const res = await fetch("/api/novels");
      const data = await res.json();
      setNovels(data.novels || []);
    } catch {
      setNovels([]);
    }
  };

  // 加载小说详情
  const loadDetail = async (id: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/novels/${id}`);
      const data = await res.json();
      setDetail(data);
      setActiveChapterIdx(0);
      setIsEditing(false);
      if (data.chapters?.length) {
        setEditingContent(data.chapters[0].content || "");
      }
    } catch {
      setDetail(null);
    }
    setLoading(false);
  };

  useEffect(() => { loadNovels(); }, []);

  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
  }, [selectedId]);

  // 切换章节
  const switchChapter = (idx: number) => {
    setActiveChapterIdx(idx);
    setIsEditing(false);
    if (detail?.chapters?.[idx]) {
      setEditingContent(detail.chapters[idx].content || "");
    }
  };

  // 保存章节内容
  const saveChapter = async () => {
    if (!detail || !detail.chapters[activeChapterIdx]) return;
    const ch = detail.chapters[activeChapterIdx];
    try {
      await fetch(`/api/novels/${detail.novel.id}/chapters/${ch.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editingContent }),
      });
      setIsEditing(false);
      loadDetail(selectedId); // 刷新
    } catch (e: any) {
      alert("保存失败: " + e.message);
    }
  };

  // 删除小说
  const deleteNovel = async (id: string) => {
    if (!confirm("确定删除这部小说？此操作不可恢复。")) return;
    try {
      await fetch(`/api/novels/${id}`, { method: "DELETE" });
      setNovels((prev) => prev.filter((n) => n.id !== id));
      if (selectedId === id) { setSelectedId(""); setDetail(null); }
    } catch (e: any) {
      alert("删除失败: " + e.message);
    }
  };

  // 多选切换
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // 全选/取消全选
  const toggleSelectAll = () => {
    if (selectedIds.size === novels.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(novels.map((n) => n.id)));
    }
  };

  // 批量删除
  const batchDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`确定删除选中的 ${selectedIds.size} 本小说？此操作不可恢复。`)) return;
    try {
      await fetch("/api/novels/batch-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([...selectedIds]),
      });
      setNovels((prev) => prev.filter((n) => !selectedIds.has(n.id)));
      if (selectedIds.has(selectedId)) { setSelectedId(""); setDetail(null); }
      setSelectedIds(new Set());
    } catch (e: any) {
      alert("批量删除失败: " + e.message);
    }
  };

  // 导出 Markdown
  const exportMarkdown = async (id: string) => {
    try {
      const res = await fetch(`/api/orchestrator/export?novel_id=${id}`);
      const data = await res.json();
      if (data.markdown) {
        const blob = new Blob([data.markdown], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${data.title || "novel"}.md`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (e: any) {
      alert("导出失败: " + e.message);
    }
  };

  const currentChapter = detail?.chapters?.[activeChapterIdx];

  return (
    <div style={S.layout}>
      {/* ─── 左侧：小说列表 ─── */}
      <div style={S.sidebar}>
        <div style={S.sidebarHeader}>
          <div style={{ fontSize: 15, fontWeight: 800, marginBottom: 2 }}>📚 小说管理</div>
          <div style={{ fontSize: 12, opacity: 0.85 }}>共 {novels.length} 部小说</div>
        </div>
        <div style={S.sidebarBody}>
          {novels.length === 0 ? (
            <div style={{ color: "#9ca3af", fontSize: 13, textAlign: "center", padding: 20 }}>
              暂无小说，请先创作
            </div>
          ) : (
            <div>
              {/* 批量操作栏 */}
              {selectedIds.size > 0 && (
                <div style={{ padding: "8px 12px", background: "#eff6ff", borderBottom: "1px solid #bfdbfe", display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                  <span style={{ color: "#1d4ed8", flex: 1 }}>已选 {selectedIds.size} 项</span>
                  <button onClick={toggleSelectAll} style={{ padding: "4px 8px", border: "1px solid #93c5fd", borderRadius: 4, background: "#fff", cursor: "pointer", color: "#2563eb" }}>全选 ({novels.length})</button>
                  <button onClick={() => setSelectedIds(new Set())} style={{ padding: "4px 8px", border: "1px solid #d1d5db", borderRadius: 4, background: "#fff", cursor: "pointer", color: "#6b7280" }}>取消选择</button>
                  <button onClick={batchDelete} style={{ padding: "4px 12px", border: "none", borderRadius: 4, background: "#ef4444", cursor: "pointer", color: "#fff", fontWeight: 600 }}>删除 {selectedIds.size} 项</button>
                </div>
              )}
              {novels.map((n) => (
                <div key={n.id} style={{ display: "flex", alignItems: "center", borderBottom: "1px solid #f3f4f6" }}>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(n.id)}
                    onChange={() => toggleSelect(n.id)}
                    style={{ margin: "0 10px", cursor: "pointer", width: 16, height: 16 }}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <div
                    style={{ ...selectedId === n.id ? S.novelCardActive : S.novelCard, flex: 1, borderBottom: "none" }}
                    onClick={() => setSelectedId(n.id)}
                  >
                    <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>{n.title}</div>
                    <div style={{ display: "flex", gap: 8, fontSize: 12, color: "#6b7280" }}>
                      <span>{n.genre || "未分类"}</span>
                      <span>·</span>
                      <span>{(n.current_word_count || 0).toLocaleString()} 字</span>
                    </div>
                    <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
                      <span style={{
                        ...S.chip,
                        background: n.status === "completed" ? "#d1fae5" : "#fef3c7",
                        color: n.status === "completed" ? "#065f46" : "#92400e",
                        fontSize: 11,
                      }}>
                        {n.status === "completed" ? "已完成" : n.status || "未知"}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ─── 右侧：小说详情 ─── */}
      <div style={S.main}>
        <div style={S.mainHeader}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#1f2937" }}>
            {detail ? detail.novel.title : "选择一部小说查看"}
          </div>
          {detail && (
            <div>
              <button style={S.btnSecondary} onClick={() => exportMarkdown(detail.novel.id)}>📥 导出</button>
              <button style={S.btnDanger} onClick={() => deleteNovel(detail.novel.id)}>🗑 删除</button>
            </div>
          )}
        </div>

        <div style={S.mainBody}>
          {!detail && !loading && (
            <div style={S.emptyState}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>📚</div>
              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>选择小说</div>
              <div style={{ fontSize: 13 }}>从左侧列表选择一部小说查看详情</div>
            </div>
          )}

          {loading && (
            <div style={S.emptyState}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>⏳</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>加载中…</div>
            </div>
          )}

          {detail && !loading && (
            <>
              {/* 小说信息 */}
              <div style={S.card}>
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <div>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>类型</div>
                    <div style={{ fontWeight: 600 }}>{detail.novel.genre || "未分类"}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>状态</div>
                    <div style={{ fontWeight: 600 }}>{detail.novel.status === "completed" ? "已完成" : detail.novel.status}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>总字数</div>
                    <div style={{ fontWeight: 600 }}>{(detail.novel.current_word_count || 0).toLocaleString()}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>章节数</div>
                    <div style={{ fontWeight: 600 }}>{detail.chapters.length}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>角色数</div>
                    <div style={{ fontWeight: 600 }}>{detail.characters.length}</div>
                  </div>
                </div>
              </div>

              {/* 内容视图切换 */}
              <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
                {[
                  { id: "chapters" as const, label: "📖 章节" },
                  { id: "characters" as const, label: "👥 角色" },
                  { id: "world" as const, label: "🌍 世界观" },
                  { id: "style" as const, label: "🎨 风格" },
                ].map((v) => (
                  <button
                    key={v.id}
                    style={activeView === v.id ? S.chapterTabActive : S.chapterTab}
                    onClick={() => setActiveView(v.id)}
                  >
                    {v.label}
                  </button>
                ))}
              </div>

              {/* 章节视图 */}
              {activeView === "chapters" && (
                <>
                  {/* 章节选择 */}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 16 }}>
                    {detail.chapters.map((ch, i) => (
                      <button
                        key={ch.id}
                        style={activeChapterIdx === i ? S.chapterTabActive : S.chapterTab}
                        onClick={() => switchChapter(i)}
                      >
                        {ch.title || `第${i + 1}章`}
                      </button>
                    ))}
                  </div>

                  {currentChapter && (
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                        <div style={{ fontSize: 16, fontWeight: 700, color: "#1f2937" }}>
                          {currentChapter.title}
                        </div>
                        <div style={{ display: "flex", gap: 8 }}>
                          <span style={{ fontSize: 12, color: "#6b7280" }}>
                            {(currentChapter.word_count || 0).toLocaleString()} 字
                          </span>
                          {!isEditing ? (
                            <button style={S.btn} onClick={() => { setEditingContent(currentChapter.content || ""); setIsEditing(true); }}>
                              ✏️ 编辑
                            </button>
                          ) : (
                            <>
                              <button style={S.btn} onClick={saveChapter}>💾 保存</button>
                              <button style={S.btnSecondary} onClick={() => setIsEditing(false)}>取消</button>
                            </>
                          )}
                        </div>
                      </div>

                      {currentChapter.outline && (
                        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 12, padding: "8px 12px", background: "#fef3c7", borderRadius: 6 }}>
                          大纲：{currentChapter.outline}
                        </div>
                      )}

                      {isEditing ? (
                        <textarea
                          style={S.textarea}
                          value={editingContent}
                          onChange={(e) => setEditingContent(e.target.value)}
                        />
                      ) : (
                        <div style={{
                          fontSize: 15, lineHeight: 1.9, color: "#374151", whiteSpace: "pre-wrap",
                          background: "#fafafa", padding: 24, borderRadius: 8, border: "1px solid #e5e7eb",
                        }}>
                          {currentChapter.content || "（无内容）"}
                        </div>
                      )}
                    </div>
                  )}

                  {detail.chapters.length === 0 && (
                    <div style={{ color: "#9ca3af", fontSize: 13, textAlign: "center", padding: 40 }}>暂无章节</div>
                  )}
                </>
              )}

              {/* 角色视图 */}
              {activeView === "characters" && (
                <>
                  <div style={S.sectionTitle}>👥 角色</div>
                  {(detail.characters || []).filter(Boolean).map((c, i) => (
                    <div key={i} style={S.card}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                        <span style={{ fontWeight: 700, fontSize: 15 }}>{c.name || "未命名"}</span>
                        <span style={S.chip}>{c.role || "未指定"}</span>
                      </div>
                      {c.personality && <div style={{ fontSize: 13, color: "#4b5563" }}>性格：{c.personality}</div>}
                      {c.background && <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>{c.background}</div>}
                    </div>
                  ))}
                  {(!detail.characters || detail.characters.length === 0) && <div style={{ color: "#9ca3af", fontSize: 13 }}>暂无角色</div>}
                </>
              )}

              {/* 世界观视图 */}
              {activeView === "world" && (
                <>
                  <div style={S.sectionTitle}>🌍 世界观</div>
                  {detail.world_settings.map((w, i) => (
                    <div key={i} style={S.card}>
                      <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>{w.name}</div>
                      <div style={{ fontSize: 12, color: "#10b981", marginBottom: 8 }}>{w.category || ""}</div>
                      {w.description && <div style={{ fontSize: 14, color: "#374151", lineHeight: 1.6 }}>{w.description}</div>}
                      {w.rules && w.rules.length > 0 && (
                        <div style={{ marginTop: 8 }}>
                          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>规则</div>
                          {w.rules.map((r, j) => (
                            <div key={j} style={{ fontSize: 13, color: "#4b5563", padding: "4px 0", paddingLeft: 12, borderLeft: "3px solid #d1fae5" }}>{r}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {detail.world_settings.length === 0 && <div style={{ color: "#9ca3af", fontSize: 13 }}>暂无世界观</div>}
                </>
              )}

              {/* 风格视图 */}
              {activeView === "style" && (
                <>
                  <div style={S.sectionTitle}>🎨 风格指南</div>
                  {detail.style_guides.map((s, i) => (
                    <div key={i} style={S.card}>
                      {s.tone && <div><span style={{ fontWeight: 600 }}>文风：</span>{s.tone}</div>}
                      {s.pacing_preference && <div><span style={{ fontWeight: 600 }}>节奏：</span>{s.pacing_preference}</div>}
                    </div>
                  ))}
                  {detail.style_guides.length === 0 && <div style={{ color: "#9ca3af", fontSize: 13 }}>暂无风格指南</div>}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
