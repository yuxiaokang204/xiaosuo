/**
 * NovelReadPage — 阅读模式页
 * 支持章节导航侧栏、字体大小调整、阅读进度、暗色模式
 * 增强：键盘快捷键（← →）、章节导航、阅读进度保存到 localStorage
 */
import React, { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../api";

interface ChapterData {
  id: string; title: string; content?: string; word_count?: number; status?: string;
}

interface NovelDetail {
  novel: { id: string; title: string; genre?: string; current_word_count?: number };
  chapters: ChapterData[];
}

const PROGRESS_KEY = "novel_read_progress";

// 读取某本小说的阅读进度（章节索引）
const loadProgress = (novelId: string): number => {
  try {
    const raw = localStorage.getItem(PROGRESS_KEY);
    if (!raw) return 0;
    const map = JSON.parse(raw);
    const v = map[novelId];
    if (typeof v === "number" && v >= 0) return v;
  } catch {}
  return 0;
};

// 保存某本小说的阅读进度
const saveProgress = (novelId: string, idx: number) => {
  try {
    const raw = localStorage.getItem(PROGRESS_KEY);
    const map = raw ? JSON.parse(raw) : {};
    map[novelId] = idx;
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(map));
  } catch {}
};

export const NovelReadPage: React.FC = () => {
  const [novels, setNovels] = useState<any[]>([]);
  const [selectedNovel, setSelectedNovel] = useState<NovelDetail | null>(null);
  const [currentChapterIdx, setCurrentChapterIdx] = useState(0);
  const [showChapterList, setShowChapterList] = useState(true);
  const [fontSize, setFontSize] = useState(18);
  const [fontFamily, setFontFamily] = useState("serif");
  const [theme, setTheme] = useState<"light" | "sepia" | "dark">("light");
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getNovels().then((d) => setNovels(d.novels || [])).catch(() => {});
  }, []);

  const openNovel = async (id: string) => {
    try {
      const data = await api.get(`/api/novels/${id}`);
      setSelectedNovel(data);
      // 恢复上次阅读进度
      const saved = loadProgress(id);
      const chapters = data.chapters || [];
      setCurrentChapterIdx(chapters.length > 0 ? Math.min(saved, chapters.length - 1) : 0);
    } catch (e: any) {
      alert(e.message);
    }
  };

  // 切换章节时：保存进度 + 滚动到顶部
  const goToChapter = useCallback((idx: number) => {
    if (!selectedNovel) return;
    const total = selectedNovel.chapters.length;
    if (idx < 0 || idx >= total) return;
    setCurrentChapterIdx(idx);
    saveProgress(selectedNovel.novel.id, idx);
    // 滚动内容区到顶部
    if (contentRef.current) contentRef.current.scrollTop = 0;
  }, [selectedNovel]);

  // 键盘快捷键：← 上一章，→ 下一章
  useEffect(() => {
    if (!selectedNovel) return;
    const handler = (e: KeyboardEvent) => {
      // 忽略输入控件中的按键
      const target = e.target as HTMLElement;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        goToChapter(currentChapterIdx - 1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        goToChapter(currentChapterIdx + 1);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selectedNovel, currentChapterIdx, goToChapter]);

  if (!selectedNovel) {
    return (
      <div>
        <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>📖 阅读模式</h2>
        {novels.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", background: "var(--bg-primary)", borderRadius: 12 }}>
            <p style={{ fontSize: 16, marginBottom: 16 }}>暂无小说，请先创建并生成章节</p>
            <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
              <button
                onClick={() => window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "novels" } }))}
                className="btn btn-primary"
              >
                📚 前往小说管理
              </button>
              <button
                onClick={() => window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "orchestrator" } }))}
                className="btn btn-secondary"
              >
                🚀 前往全流程编排
              </button>
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {novels.map((n) => (
              <div key={n.id} className="card" style={{ cursor: "pointer" }} onClick={() => openNovel(n.id)}>
                <h4 style={{ margin: 0 }}>{n.title}</h4>
                <p style={{ fontSize: 13, color: "var(--text-muted)", margin: "4px 0 0" }}>
                  {n.genre} · {n.current_word_count ?? 0} 字 · {n.status || "构思中"}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  const chapters = selectedNovel.chapters || [];
  const current = chapters[currentChapterIdx] || null;
  const progress = chapters.length > 0 ? ((currentChapterIdx + 1) / chapters.length) * 100 : 0;

  const contentStyle: React.CSSProperties = {
    fontFamily: fontFamily === "sans" ? "system-ui, sans-serif" : "Noto Serif SC, Georgia, serif",
    fontSize,
    lineHeight: 2,
    whiteSpace: "pre-wrap",
  };

  const bgMap: Record<string, string> = {
    light: "var(--bg-primary)",
    sepia: "#f4ecd8",
    dark: "#1a1a2e",
  };
  const textMap: Record<string, string> = {
    light: "var(--text-primary)",
    sepia: "#433422",
    dark: "#e0e0e0",
  };

  return (
    <div style={{ display: "flex", gap: 0, height: "calc(100vh - 104px)", overflow: "hidden" }}>
      {/* 章节侧栏 */}
      <div style={{
        width: showChapterList ? 240 : 0,
        minWidth: showChapterList ? 240 : 0,
        background: "var(--bg-primary)",
        borderRight: "1px solid var(--border)",
        overflowY: "auto",
        transition: "all 250ms ease",
        display: "flex",
        flexDirection: "column",
      }}>
        <div style={{
          padding: "12px 16px",
          borderBottom: "1px solid var(--border)",
          fontSize: 13,
          fontWeight: 600,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexShrink: 0,
        }}>
          <span>章节列表</span>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{chapters.length} 章</span>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
          {chapters.map((ch, idx) => (
            <div
              key={ch.id}
              onClick={() => goToChapter(idx)}
              style={{
                padding: "10px 12px",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                marginBottom: 2,
                background: currentChapterIdx === idx ? "var(--accent-light)" : "transparent",
                color: currentChapterIdx === idx ? "var(--accent)" : "var(--text-primary)",
                fontWeight: currentChapterIdx === idx ? 600 : 400,
                borderLeft: currentChapterIdx === idx ? "3px solid var(--accent)" : "3px solid transparent",
                transition: "all 150ms ease",
              }}
            >
              <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {ch.title}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                {ch.word_count ?? 0} 字
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 主阅读区 */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* 工具栏 */}
        <div style={{
          padding: "8px 20px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "var(--bg-secondary)",
          flexShrink: 0,
          gap: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              onClick={() => setShowChapterList(!showChapterList)}
              className="btn btn-ghost btn-sm"
              title="章节列表"
            >
              {showChapterList ? "◀" : "☰"}
            </button>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {current ? `${currentChapterIdx + 1}/${chapters.length}` : "0/0"}
            </span>
          </div>

          {/* 上一章/下一章 */}
          <div style={{ display: "flex", gap: 4 }}>
            <button
              disabled={currentChapterIdx <= 0}
              onClick={() => goToChapter(currentChapterIdx - 1)}
              className="btn btn-secondary btn-sm"
              style={{ opacity: currentChapterIdx <= 0 ? 0.4 : 1 }}
              title="快捷键 ←"
            >
              ← 上一章
            </button>
            <button
              disabled={currentChapterIdx >= chapters.length - 1}
              onClick={() => goToChapter(currentChapterIdx + 1)}
              className="btn btn-secondary btn-sm"
              style={{ opacity: currentChapterIdx >= chapters.length - 1 ? 0.4 : 1 }}
              title="快捷键 →"
            >
              下一章 →
            </button>
          </div>

          {/* 显示设置 */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button onClick={() => setFontSize((s) => Math.max(14, s - 2))} className="btn btn-ghost btn-sm" title="减小字体">A-</button>
            <button onClick={() => setFontSize((s) => Math.min(28, s + 2))} className="btn btn-ghost btn-sm" title="增大字体">A+</button>
            <select
              value={fontFamily}
              onChange={(e) => setFontFamily(e.target.value)}
              className="select"
              style={{ width: 100, padding: "4px 8px", fontSize: 12 }}
            >
              <option value="serif">衬线体</option>
              <option value="sans">无衬线</option>
            </select>
            <select
              value={theme}
              onChange={(e) => setTheme(e.target.value as any)}
              className="select"
              style={{ width: 100, padding: "4px 8px", fontSize: 12 }}
            >
              <option value="light">白底</option>
              <option value="sepia">羊皮</option>
              <option value="dark">暗色</option>
            </select>
          </div>
        </div>

        {/* 阅读进度条 */}
        <div style={{
          height: 3, background: "var(--bg-tertiary)", flexShrink: 0,
        }}>
          <div style={{
            height: "100%", width: `${progress}%`,
            background: "var(--accent)",
            transition: "width 300ms ease",
          }} />
        </div>

        {/* 内容区 */}
        <div
          ref={contentRef}
          style={{
          flex: 1,
          overflowY: "auto",
          background: bgMap[theme],
          color: textMap[theme],
          padding: "40px 48px",
        }}>
          {current ? (
            <div style={{
              maxWidth: 760,
              margin: "0 auto",
            }}>
              <h2 style={{
                textAlign: "center",
                marginBottom: 32,
                fontSize: 24,
                fontWeight: 700,
                color: textMap[theme],
              }}>
                {current.title}
              </h2>
              <div style={contentStyle}>
                {current.content || "（内容尚未生成）"}
              </div>
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted)" }}>
              该小说暂无章节内容
            </div>
          )}
        </div>

        {/* 页脚 */}
        <div style={{
          padding: "6px 20px",
          borderTop: "1px solid var(--border)",
          fontSize: 11,
          color: "var(--text-muted)",
          display: "flex",
          justifyContent: "space-between",
          background: "var(--bg-secondary)",
          flexShrink: 0,
        }}>
          <span>{selectedNovel.novel.title} · 共 {chapters.length} 章</span>
          <span>第 {currentChapterIdx + 1} / {chapters.length} 章 · 快捷键 ← → 切换章节</span>
        </div>
      </div>
    </div>
  );
};
