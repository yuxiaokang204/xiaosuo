/**
 * StandaloneDraftPage — 独立草稿生成页
 * 支持选择已有小说、章节标题/大纲输入、流式生成、保存到章节
 */
import React, { useState, useEffect } from "react";

interface NovelSummary {
  id: string; title: string; genre?: string; current_word_count?: number;
}

export const StandaloneDraftPage: React.FC = () => {
  const [novels, setNovels] = useState<NovelSummary[]>([]);
  const [selectedNovelId, setSelectedNovelId] = useState("");
  const [chapterTitle, setChapterTitle] = useState("");
  const [chapterOutline, setChapterOutline] = useState("");
  const [prevChapterSummaries, setPrevChapterSummaries] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载小说列表
  useEffect(() => {
    fetch("/api/novels").then((r) => r.json()).then((d) => setNovels(d.novels || [])).catch(() => {});
  }, []);

  // 当选择小说时，获取已有章节摘要
  useEffect(() => {
    if (selectedNovelId) {
      fetch(`/api/novels/${selectedNovelId}`).then(async (r) => {
        try {
          const data = await r.json();
          const chs = data.chapters || [];
          if (chs.length > 0) {
            const summaries = chs.map((c: any) => `第${chs.indexOf(c) + 1}章 ${c.title}: ${c.outline || c.content?.slice(0, 100) || ""}`).join("\n");
            setPrevChapterSummaries(summaries);
          }
        } catch { /* ignore */ }
      }).catch(() => {});
    }
  }, [selectedNovelId]);

  const generate = async () => {
    if (!chapterTitle.trim()) return;
    setLoading(true);
    setError(null);
    setContent("");

    const body = {
      chapter_title: chapterTitle.trim(),
      chapter_outline: chapterOutline,
      summaries: selectedNovelId ? (prevChapterSummaries || "") : "",
      characters: "",
      world: "",
      foreshadowing: "",
      style_guide: "",
    };

    // 使用 POST + fetch 流式读取（SSE 兼容性更好）
    try {
      const r = await fetch("/api/create/draft-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: "HTTP " + r.status }));
        throw new Error(err.detail || err.error || "请求失败");
      }

      const reader = r.body?.getReader();
      if (!reader) throw new Error("无法读取流");

      const decoder = new TextDecoder();
      let fullContent = "";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const jsonStr = line.slice(6);
            try {
              const data = JSON.parse(jsonStr);
              if (data.token) {
                fullContent += data.token;
                setContent(fullContent);
              }
              if (data.error) {
                setError(data.error);
              }
            } catch { /* 跳过非 JSON 行 */ }
          }
        }
      }

      // 处理缓冲区剩余数据
      if (buffer.startsWith("data: ")) {
        try {
          const data = JSON.parse(buffer.slice(6));
          if (data.token) {
            fullContent += data.token;
            setContent(fullContent);
          }
        } catch { /* ignore */ }
      }
    } catch (e: any) {
      if (!content) {
        setError(e.message || "生成失败，请检查 LLM 配置");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>✍️ 独立草稿生成</h2>

      {/* 参数区 */}
      <div style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: 12, padding: 24, marginBottom: 24 }}>
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 12 }}>
            <div>
              <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>选择小说（可选）</label>
              <select
                value={selectedNovelId}
                onChange={(e) => setSelectedNovelId(e.target.value)}
                className="select"
                disabled={loading}
              >
                <option value="">不关联小说（纯独立生成）</option>
                {novels.map((n) => (
                  <option key={n.id} value={n.id}>{n.title}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 12 }}>
            <div>
              <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>章节标题 *</label>
              <input
                type="text"
                value={chapterTitle}
                onChange={(e) => setChapterTitle(e.target.value)}
                className="input"
                placeholder="第1章 初入江湖"
                disabled={loading}
              />
            </div>
            <div>
              <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>章节大纲</label>
              <input
                type="text"
                value={chapterOutline}
                onChange={(e) => setChapterOutline(e.target.value)}
                className="input"
                placeholder="本章内容概要"
                disabled={loading}
              />
            </div>
          </div>

          {prevChapterSummaries && (
            <div>
              <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>前情概要（自动加载）</label>
              <div style={{
                padding: 12, background: "var(--bg-tertiary)",
                borderRadius: 8, fontSize: 12, lineHeight: 1.6,
                maxHeight: 120, overflowY: "auto",
                color: "var(--text-secondary)",
                whiteSpace: "pre-wrap",
              }}>
                {prevChapterSummaries}
              </div>
            </div>
          )}

          <button
            onClick={generate}
            disabled={loading || !chapterTitle.trim()}
            className="btn btn-primary btn-lg"
          >
            {loading ? "⏳ 生成中..." : "📝 生成草稿"}
          </button>
        </div>
      </div>

      {/* 错误 */}
      {error && (
        <div style={{ padding: 16, background: "var(--danger-light)", borderRadius: 8, color: "var(--danger)", marginBottom: 16 }}>
          ❌ {error}
        </div>
      )}

      {/* 结果区 */}
      {(content || loading) && (
        <div style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: 12, padding: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12, alignItems: "center" }}>
            <h3 style={{ fontSize: 16, margin: 0 }}>
              生成结果 {content && <span style={{ fontSize: 12, color: "var(--text-muted)" }}>({content.length} 字)</span>}
            </h3>
            {content && (
              <button
                onClick={() => {
                  navigator.clipboard.writeText(content);
                }}
                className="btn btn-ghost btn-sm"
              >
                📋 复制
              </button>
            )}
          </div>
          <div style={{
            whiteSpace: "pre-wrap", lineHeight: 1.8, fontSize: 15,
            maxHeight: "calc(100vh - 320px)", overflowY: "auto",
          }}>
            {content || <span style={{ color: "var(--text-muted)" }}>正在生成...</span>}
          </div>
        </div>
      )}
    </div>
  );
};
