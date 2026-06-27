/**
 * NovelManagerPage — 小说管理页
 * 支持小说 CRUD、详情查看、章节列表、导出 Markdown
 */
import React, { useState, useEffect, useCallback } from "react";
import { api } from "../api";

interface NovelSummary {
  id: string; title: string; genre?: string; status?: string;
  current_word_count?: number; target_word_count?: number; updated_at?: string;
}

interface ChapterData {
  id: string; title: string; content?: string; word_count?: number; status?: string; outline?: string;
}

interface NovelDetail {
  novel: NovelSummary;
  chapters: ChapterData[];
  characters: any[];
  world_settings: any[];
  style_guides: any[];
}

export const NovelManagerPage: React.FC = () => {
  const [novels, setNovels] = useState<NovelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newGenre, setNewGenre] = useState("");
  const [selectedNovel, setSelectedNovel] = useState<NovelDetail | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"chapters" | "characters" | "world" | "style">("chapters");
  const [chapterContentLoading, setChapterContentLoading] = useState(false);
  const [chapterContentData, setChapterContentData] = useState<any>(null);
  const [showChapterContent, setShowChapterContent] = useState(false);

  const fetchNovels = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getNovels();
      setNovels(data.novels || []);
      setError(null);
    } catch (e: any) {
      setError(e.message || "加载小说列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchNovels(); }, [fetchNovels]);

  const createNovel = async () => {
    if (!newTitle.trim()) return;
    try {
      const data = await api.createNovel(newTitle.trim(), newGenre);
      setNovels((prev) => [...prev, data]);
      setShowCreate(false);
      setNewTitle("");
      setNewGenre("");
      setError(null);
    } catch (e: any) {
      setError(e.message || "创建失败");
    }
  };

  const deleteNovel = async (id: string) => {
    if (!confirm("确定删除该小说及其所有数据？")) return;
    try {
      await api.delete(`/api/novels/${id}`);
      // 只过滤本地状态，不重新请求全量列表（避免组件重新挂载导致 ErrorBoundary 触发）
      setNovels((prev) => {
        if (!Array.isArray(prev)) return [];
        return prev.filter((n) => n.id !== id);
      });
      // 删除后清理所有相关状态，防止渲染已删除小说的数据
      if (selectedNovel?.novel?.id === id || selectedNovel?.novel?.id === undefined) {
        setSelectedNovel(null);
        setShowDetail(false);
        setShowChapterContent(false);
        setChapterContentData(null);
      }
      setError(null);
    } catch (e: any) {
      console.error("[NovelManagerPage] 删除小说失败:", e);
      setError(e.message || "删除失败");
    }
  };

  const openNovel = async (id: string) => {
    setDetailLoading(true);
    try {
      const data = await api.get(`/api/novels/${id}`);
      setSelectedNovel(data);
      setShowDetail(true);
      setActiveTab("chapters");
      setError(null);
    } catch (e: any) {
      setError(e.message || "获取小说详情失败");
    } finally {
      setDetailLoading(false);
    }
  };

  const fetchChapterContent = async (novelId: string, chapterId: string, title: string) => {
    setChapterContentLoading(true);
    setShowChapterContent(true);
    setChapterContentData({ title, content: "" });
    try {
      const data = await api.get(`/api/novels/${novelId}/chapters/${chapterId}/content`);
      setChapterContentData(data);
      setError(null);
    } catch (e: any) {
      setChapterContentData({ title, content: "加载失败：" + (e.message || "未知错误") });
    } finally {
      setChapterContentLoading(false);
    }
  };

  const exportNovel = async (id: string, title: string, format: "txt" | "markdown") => {
    try {
      const resp = await fetch(`/api/novels/${id}/export?format=${format}`);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: "导出失败" }));
        throw new Error(err.detail || "导出失败");
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${title}.${format === "markdown" ? "md" : "txt"}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e.message || "导出失败，请确保小说已生成章节内容");
    }
  };

  const exportMarkdown = async () => {
    if (!selectedNovel) return;
    // 更新 TopBar 标题
    window.dispatchEvent(new CustomEvent("novel-title", { detail: { title: selectedNovel.novel.title } }));
    await exportNovel(selectedNovel.novel.id, selectedNovel.novel.title, "markdown");
  };

  const exportTxt = async () => {
    if (!selectedNovel) return;
    await exportNovel(selectedNovel.novel.id, selectedNovel.novel.title, "txt");
  };

  const tabs = [
    { key: "chapters" as const, label: `📄 章节 (${selectedNovel?.chapters.length ?? 0})` },
    { key: "characters" as const, label: `👥 角色 (${selectedNovel?.characters.length ?? 0})` },
    { key: "world" as const, label: `🌍 世界观 (${selectedNovel?.world_settings.length ?? 0})` },
    { key: "style" as const, label: `🎨 风格指南 (${selectedNovel?.style_guides.length ?? 0})` },
  ];

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>📚 小说管理</h2>

      {/* 错误提示 */}
      {error && (
        <div style={{
          padding: 12, marginBottom: 16,
          background: "var(--danger-light)", borderRadius: 8,
          color: "var(--danger)", fontSize: 14,
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span>❌ {error}</span>
          <button onClick={() => setError(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--danger)" }}>✕</button>
        </div>
      )}

      {/* 创建按钮 */}
      <div style={{ marginBottom: 20, display: "flex", gap: 8 }}>
        <button onClick={() => setShowCreate(true)} className="btn btn-primary">
          + 新建小说
        </button>
      </div>

      {/* 创建模态框 */}
      {showCreate && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: 400 }}>
            <div className="modal-header">
              <h3 style={{ fontSize: 16, margin: 0 }}>新建小说</h3>
              <button onClick={() => setShowCreate(false)} className="btn btn-ghost">✕</button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>标题</label>
                <input type="text" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} className="input" placeholder="输入小说标题" />
              </div>
              <div>
                <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>类型</label>
                <input type="text" value={newGenre} onChange={(e) => setNewGenre(e.target.value)} className="input" placeholder="玄幻、都市、科幻..." />
              </div>
            </div>
            <div className="modal-footer">
              <button onClick={() => setShowCreate(false)} className="btn btn-secondary">取消</button>
              <button onClick={createNovel} className="btn btn-primary">创建</button>
            </div>
          </div>
        </div>
      )}

      {/* 小说列表 */}
      {loading ? (
        <div className="skeleton" style={{ height: 200, borderRadius: 12 }} />
      ) : novels.length === 0 ? (
        <div style={{
          padding: 40, textAlign: "center", color: "var(--text-muted)",
          background: "var(--bg-primary)", borderRadius: 12,
        }}>
          暂无小说，点击「新建小说」开始
        </div>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {novels.map((n) => (
            <div key={n.id} className="card" style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              cursor: "pointer",
            }} onClick={() => openNovel(n.id)}>
              <div>
                <h4 style={{ margin: 0, fontSize: 16 }}>{n.title}</h4>
                <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>
                  {n.genre} · {n.current_word_count ?? 0} 字 · {n.status || "构思中"}
                </div>
              </div>
              <div style={{ display: "flex", gap: 4 }} onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => exportNovel(n.id, n.title, "txt")}
                  className="btn btn-secondary btn-sm"
                  title="导出 TXT"
                >
                  📄
                </button>
                <button
                  onClick={() => exportNovel(n.id, n.title, "markdown")}
                  className="btn btn-secondary btn-sm"
                  title="导出 Markdown"
                >
                  📥
                </button>
                <button onClick={() => deleteNovel(n.id)} className="btn btn-danger btn-sm">删除</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 小说详情 */}
      {showDetail && selectedNovel && (
        <div className="modal-overlay" onClick={() => setShowDetail(false)}>
          <div className="modal-content" style={{ maxWidth: 800 }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3 style={{ fontSize: 18, margin: 0 }}>{selectedNovel.novel.title}</h3>
                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  {selectedNovel.novel.genre} · {selectedNovel.novel.current_word_count ?? 0} 字 · {selectedNovel.novel.status || "构思中"}
                </span>
              </div>
              <button onClick={() => setShowDetail(false)} className="btn btn-ghost">✕</button>
            </div>

            {/* 标签页 */}
            <div style={{
              display: "flex", gap: 0, borderBottom: "1px solid var(--border)",
              padding: "0 24px",
            }}>
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: "12px 16px",
                    border: "none",
                    background: "transparent",
                    borderBottom: activeTab === tab.key ? "2px solid var(--accent)" : "2px solid transparent",
                    color: activeTab === tab.key ? "var(--accent)" : "var(--text-secondary)",
                    fontWeight: activeTab === tab.key ? 600 : 400,
                    cursor: "pointer",
                    fontSize: 13,
                    transition: "all 150ms ease",
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="modal-body">
              {detailLoading ? (
                <div style={{ padding: 40, textAlign: "center" }}>
                  <span className="spinner" />
                  <p style={{ marginTop: 12, color: "var(--text-muted)" }}>加载详情中...</p>
                </div>
              ) : (
              <>
              {/* 章节标签页 */}
              {activeTab === "chapters" && (
                selectedNovel.chapters.length === 0 ? (
                  <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>
                    <p style={{ marginBottom: 16 }}>暂无章节，请前往「全流程编排」生成</p>
                    <button
                      onClick={() => {
                        setShowDetail(false);
                        window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "orchestrator" } }));
                      }}
                      className="btn btn-primary btn-sm"
                    >
                      🚀 前往全流程编排
                    </button>
                  </div>
                ) : (
                  <div style={{ display: "grid", gap: 8 }}>
                    {selectedNovel.chapters.map((ch) => (
                      <div key={ch.id} style={{
                        padding: 12, background: "var(--bg-secondary)",
                        borderRadius: 8, cursor: "pointer",
                      }}
                        onClick={() => fetchChapterContent(selectedNovel.novel.id, ch.id, ch.title)}
                      >
                        <div style={{ fontWeight: 600, fontSize: 14 }}>{ch.title}</div>
                        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                          {ch.word_count ?? 0} 字 · {ch.status || "draft"}
                          {ch.outline && ` · ${ch.outline.slice(0, 50)}${ch.outline.length > 50 ? "..." : ""}`}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              )}

              {/* 角色标签页 */}
              {activeTab === "characters" && (
                selectedNovel.characters.length === 0 ? (
                  <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>暂无角色</div>
                ) : (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
                    {selectedNovel.characters.map((c, idx) => (
                      <div key={idx} style={{ padding: 16, background: "var(--bg-secondary)", borderRadius: 8 }}>
                        <div style={{ fontWeight: 600 }}>{c.name}</div>
                        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>{c.role}</div>
                        {c.personality && (
                          <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 8, lineHeight: 1.6 }}>
                            {c.personality.slice(0, 100)}{c.personality.length > 100 ? "..." : ""}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )
              )}

              {/* 世界观标签页 */}
              {activeTab === "world" && (
                selectedNovel.world_settings.length === 0 ? (
                  <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>暂无世界观</div>
                ) : (
                  <div style={{ display: "grid", gap: 12 }}>
                    {selectedNovel.world_settings.map((w, idx) => (
                      <div key={idx} style={{ padding: 16, background: "var(--bg-secondary)", borderRadius: 8 }}>
                        <div style={{ fontWeight: 600, fontSize: 15 }}>{w.name} <span className="badge badge-info" style={{ marginLeft: 8 }}>{w.category}</span></div>
                        {w.description && (
                          <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 8, lineHeight: 1.6 }}>
                            {w.description.slice(0, 300)}{w.description.length > 300 ? "..." : ""}
                          </div>
                        )}
                        {w.rules && w.rules.length > 0 && (
                          <div style={{ marginTop: 8 }}>
                            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>规则：</div>
                            {w.rules.map((r: string, i: number) => (
                              <div key={i} style={{ fontSize: 13, padding: "2px 0", color: "var(--text-secondary)" }}>• {r}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )
              )}

              {/* 风格指南标签页 */}
              {activeTab === "style" && (
                selectedNovel.style_guides.length === 0 ? (
                  <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)" }}>暂无风格指南</div>
                ) : (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
                    {selectedNovel.style_guides.map((s, idx) => (
                      <div key={idx} style={{ padding: 16, background: "var(--bg-secondary)", borderRadius: 8 }}>
                        <div style={{ fontWeight: 600 }}>文风</div>
                        <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 8 }}>{s.tone || "-"}</div>
                        {s.pacing_preference && (
                          <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>节奏：{s.pacing_preference}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )
              )}
              </>
              )}
            </div>

            <div className="modal-footer">
              <button onClick={exportTxt} className="btn btn-secondary">📄 导出 TXT</button>
              <button onClick={exportMarkdown} className="btn btn-primary">📥 导出 Markdown</button>
              <button onClick={() => setShowDetail(false)} className="btn btn-ghost">关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* 章节内容弹窗 */}
      {showChapterContent && chapterContentData && (
        <div className="modal-overlay" onClick={() => setShowChapterContent(false)}>
          <div className="modal-content" style={{ maxWidth: 800, maxHeight: "80vh" }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: 18, margin: 0 }}>{chapterContentData.title}</h3>
              <button onClick={() => setShowChapterContent(false)} className="btn btn-ghost">✕</button>
            </div>
            <div className="modal-body" style={{ maxHeight: "60vh", overflowY: "auto" }}>
              {chapterContentLoading ? (
                <div style={{ padding: 40, textAlign: "center" }}>
                  <span className="spinner" />
                  <p style={{ marginTop: 12, color: "var(--text-muted)" }}>加载章节内容...</p>
                </div>
              ) : (
                <div style={{
                  fontFamily: "Noto Serif SC, Georgia, serif",
                  fontSize: 16,
                  lineHeight: 2,
                  whiteSpace: "pre-wrap",
                  color: "var(--text-primary)",
                }}>
                  {chapterContentData.content || "（暂无内容）"}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {chapterContentData.word_count != null ? `${chapterContentData.word_count} 字` : ""}
              </span>
              <button onClick={() => setShowChapterContent(false)} className="btn btn-secondary">关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};