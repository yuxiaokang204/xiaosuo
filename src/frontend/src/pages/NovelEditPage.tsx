/**
 * NovelEditPage — 章节编辑器
 */
import React, { useState, useEffect } from "react";

export const NovelEditPage: React.FC = () => {
  const [novels, setNovels] = useState<any[]>([]);
  const [selectedNovel, setSelectedNovel] = useState<any>(null);
  const [chapters, setChapters] = useState<any[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<any>(null);
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [viewMode, setViewMode] = useState<"edit" | "preview">("edit");

  useEffect(() => {
    fetch("/api/novels").then((r) => r.json()).then((d) => setNovels(d.novels || [])).catch(() => {});
  }, []);

  const openNovel = async (id: string) => {
    try {
      const data = await fetch(`/api/novels/${id}`).then((r) => r.json());
      setSelectedNovel(data);
      const vols = data.volumes || [];
      const allChapters: any[] = [];
      for (const v of vols) {
        const chData = v.chapters || [];
        chData.forEach((ch: any) => allChapters.push({ ...ch, volumeTitle: v.title }));
      }
      allChapters.sort((a, b) => (a.order || 0) - (b.order || 0));
      setChapters(allChapters);
      setSelectedChapter(null);
      setContent("");
    } catch (e: any) {
      alert(e.message);
    }
  };

  const selectChapter = (ch: any) => {
    setSelectedChapter(ch);
    setContent(ch.content || "");
    setViewMode("edit");
  };

  const saveChapter = async () => {
    if (!selectedNovel || !selectedChapter) return;
    setSaving(true);
    try {
      await fetch(`/api/novels/${selectedNovel.id}/chapters/${selectedChapter.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
    } catch (e: any) {
      alert(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>📝 章节编辑</h2>

      {/* 小说选择 */}
      {!selectedNovel ? (
        <div style={{ display: "grid", gap: 12 }}>
          {novels.map((n) => (
            <div key={n.id} className="card" style={{ cursor: "pointer" }} onClick={() => openNovel(n.id)}>
              <h4 style={{ margin: 0 }}>{n.title}</h4>
              <p style={{ fontSize: 13, color: "var(--text-muted)", margin: "4px 0 0" }}>
                {n.genre} · {n.current_word_count ?? 0} 字
              </p>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: "flex", gap: 16 }}>
          {/* 章节列表 */}
          <div style={{
            width: 220, flexShrink: 0,
            background: "var(--bg-primary)",
            border: "1px solid var(--border)",
            borderRadius: 12,
            padding: 12,
            maxHeight: "calc(100vh - 160px)",
            overflowY: "auto",
          }}>
            <div style={{
              fontSize: 13, fontWeight: 600, marginBottom: 8,
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <span>{selectedNovel.title}</span>
              <button onClick={() => setSelectedNovel(null)} style={{
                background: "none", border: "none", cursor: "pointer",
                fontSize: 14, color: "var(--text-muted)",
              }}>✕</button>
            </div>
            {chapters.map((ch) => (
              <div
                key={ch.id}
                onClick={() => selectChapter(ch)}
                style={{
                  padding: "8px 10px",
                  borderRadius: 6,
                  cursor: "pointer",
                  fontSize: 13,
                  marginBottom: 2,
                  background: selectedChapter?.id === ch.id ? "var(--accent-light)" : "transparent",
                  color: selectedChapter?.id === ch.id ? "var(--accent)" : "var(--text-primary)",
                  fontWeight: selectedChapter?.id === ch.id ? 600 : 400,
                }}
              >
                {ch.title}
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                  {ch.content ? `${ch.word_count ?? 0} 字` : "未写"}
                </div>
              </div>
            ))}
          </div>

          {/* 编辑器 */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {selectedChapter ? (
              <>
                <div style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  marginBottom: 12,
                }}>
                  <h3 style={{ margin: 0, fontSize: 18 }}>{selectedChapter.title}</h3>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button onClick={() => setViewMode(viewMode === "edit" ? "preview" : "edit")} className="btn btn-secondary btn-sm">
                      {viewMode === "edit" ? "👁 预览" : "✏ 编辑"}
                    </button>
                    <button onClick={saveChapter} disabled={saving} className="btn btn-primary btn-sm">
                      {saving ? "保存中..." : "💾 保存"}
                    </button>
                  </div>
                </div>

                {viewMode === "edit" ? (
                  <textarea
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    style={{
                      width: "100%",
                      minHeight: "calc(100vh - 240px)",
                      padding: 20,
                      fontFamily: "'Noto Serif SC', serif",
                      fontSize: 16,
                      lineHeight: 2,
                      background: "var(--bg-primary)",
                      color: "var(--text-primary)",
                      border: "1px solid var(--border)",
                      borderRadius: 12,
                      resize: "vertical",
                      outline: "none",
                    }}
                    placeholder="在此输入章节内容..."
                  />
                ) : (
                  <div className="reader-mode">
                    {content || "（暂无内容）"}
                  </div>
                )}

                <div style={{
                  marginTop: 8, fontSize: 12, color: "var(--text-muted)",
                  textAlign: "right",
                }}>
                  {content.length} 字
                </div>
              </>
            ) : (
              <div style={{
                padding: 60, textAlign: "center", color: "var(--text-muted)",
                background: "var(--bg-primary)", borderRadius: 12,
              }}>
                选择左侧章节开始编辑
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
