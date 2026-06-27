import React, { useState, useRef, useEffect } from "react";

// ──────────── 类型定义 ────────────

export interface TimelineEvent {
  chapter: number;
  title: string;
  content?: string;
  characters: string[];
  location?: string;
  events: string[];
  foreshadowing?: string[];
}

interface NarrativeTimelineProps {
  events: TimelineEvent[];
  collapsed?: boolean;
}

// ──────────── 样式 ────────────

const S: Record<string, React.CSSProperties> = {
  container: {
    background: "#fff",
    borderRadius: 12,
    boxShadow: "0 2px 12px rgba(0,0,0,.06)",
    overflow: "hidden",
  },
  header: {
    padding: "16px 20px",
    background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    color: "#fff",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: 700,
  },
  toggleBtn: {
    background: "rgba(255,255,255,0.2)",
    border: "none",
    borderRadius: 6,
    color: "#fff",
    cursor: "pointer",
    padding: "4px 12px",
    fontSize: 12,
    fontWeight: 600,
  },
  body: {
    padding: "20px 24px",
    maxHeight: 600,
    overflowY: "auto",
  },
  emptyState: {
    textAlign: "center",
    padding: "40px 20px",
    color: "#9ca3af",
    fontSize: 14,
  },
  timeline: {
    position: "relative",
    paddingLeft: 32,
  },
  timelineLine: {
    position: "absolute",
    left: 11,
    top: 0,
    bottom: 0,
    width: 2,
    background: "#e5e7eb",
  },
  chapterItem: {
    position: "relative",
    marginBottom: 16,
  },
  chapterDot: {
    position: "absolute",
    left: -32,
    top: 16,
    width: 24,
    height: 24,
    borderRadius: "50%",
    background: "#fff",
    border: "3px solid #667eea",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 11,
    fontWeight: 700,
    color: "#667eea",
    zIndex: 1,
  },
  chapterDotCompleted: {
    position: "absolute",
    left: -32,
    top: 16,
    width: 24,
    height: 24,
    borderRadius: "50%",
    background: "#10b981",
    border: "3px solid #10b981",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 11,
    fontWeight: 700,
    color: "#fff",
    zIndex: 1,
  },
  chapterCard: {
    background: "#f9fafb",
    border: "1px solid #e5e7eb",
    borderRadius: 10,
    padding: 16,
    cursor: "pointer",
    transition: "all .2s",
  },
  chapterCardExpanded: {
    background: "#f9fafb",
    border: "2px solid #667eea",
    borderRadius: 10,
    padding: 16,
    boxShadow: "0 2px 8px rgba(102,126,234,.15)",
  },
  chapterTitle: {
    fontSize: 15,
    fontWeight: 700,
    color: "#1f2937",
    marginBottom: 6,
  },
  chapterMeta: {
    display: "flex",
    gap: 12,
    fontSize: 12,
    color: "#6b7280",
    marginBottom: 8,
    flexWrap: "wrap",
  },
  chapterEvents: {
    fontSize: 13,
    color: "#374151",
    lineHeight: 1.6,
  },
  chapterDetails: {
    marginTop: 12,
    paddingTop: 12,
    borderTop: "1px solid #e5e7eb",
  },
  charTag: {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: 999,
    background: "#e0e7ff",
    color: "#3730a3",
    fontSize: 11,
    fontWeight: 600,
    margin: "2px 4px 2px 0",
  },
  locationTag: {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: 999,
    background: "#fef3c7",
    color: "#92400e",
    fontSize: 11,
    fontWeight: 600,
    margin: "2px 4px 2px 0",
  },
  eventItem: {
    fontSize: 13,
    color: "#4b5563",
    padding: "4px 0",
    paddingLeft: 12,
    borderLeft: "3px solid #e0e7ff",
  },
  eventDot: {
    position: "absolute",
    left: -16,
    top: 10,
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#667eea",
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: 600,
    color: "#6b7280",
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  expandedContent: {
    fontSize: 13,
    color: "#374151",
    lineHeight: 1.7,
    whiteSpace: "pre-wrap",
    maxHeight: 300,
    overflowY: "auto",
    background: "#fff",
    padding: 12,
    borderRadius: 6,
    border: "1px solid #e5e7eb",
  },
  collapsed: {
    display: "none",
  },
};

// ──────────── 子组件 ────────────

function ChapterItem({
  event,
  isExpanded,
  onToggle,
}: {
  event: TimelineEvent;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div style={S.chapterItem}>
      <div style={S.chapterDot}>{event.chapter}</div>
      <div
        style={isExpanded ? S.chapterCardExpanded : S.chapterCard}
        onClick={onToggle}
      >
        <div style={S.chapterTitle}>
          第{event.chapter}章 {event.title}
        </div>
        <div style={S.chapterMeta}>
          {event.location && (
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span>📍</span> {event.location}
            </span>
          )}
          {event.characters.length > 0 && (
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span>👥</span> {event.characters.join("、")}
            </span>
          )}
        </div>
        {event.events.length > 0 && (
          <div>
            <div style={{ ...S.sectionLabel, marginBottom: 4 }}>关键事件</div>
            {event.events.slice(0, 2).map((ev, i) => (
              <div key={i} style={S.eventItem}>
                {ev}
              </div>
            ))}
            {event.events.length > 2 && (
              <div style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>
                +{event.events.length - 2} 更多事件
              </div>
            )}
          </div>
        )}
      </div>

      {isExpanded && (
        <div style={S.chapterDetails}>
          {/* 全部角色 */}
          {event.characters.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={S.sectionLabel}>登场角色</div>
              <div>
                {event.characters.map((char, i) => (
                  <span key={i} style={S.charTag}>
                    {char}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 关键事件列表 */}
          {event.events.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={S.sectionLabel}>全部事件</div>
              {event.events.map((ev, i) => (
                <div
                  key={i}
                  style={{
                    ...S.eventItem,
                    position: "relative",
                    paddingLeft: 16,
                  }}
                >
                  <span style={S.eventDot} />
                  {ev}
                </div>
              ))}
            </div>
          )}

          {/* 伏笔 */}
          {event.foreshadowing && event.foreshadowing.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={S.sectionLabel}>🔮 伏笔</div>
              {event.foreshadowing.map((f, i) => (
                <div
                  key={i}
                  style={{
                    ...S.eventItem,
                    borderLeftColor: "#f59e0b",
                    background: "#fffbeb",
                    borderRadius: 4,
                    padding: "4px 8px",
                  }}
                >
                  {f}
                </div>
              ))}
            </div>
          )}

          {/* 正文预览 */}
          {event.content && (
            <div>
              <div style={S.sectionLabel}>正文预览</div>
              <div style={S.expandedContent}>{event.content}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ──────────── 主组件 ────────────

export const NarrativeTimeline: React.FC<NarrativeTimelineProps> = ({
  events,
  collapsed: initialCollapsed = false,
}) => {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(initialCollapsed);
  const bodyRef = useRef<HTMLDivElement>(null);

  const toggleExpand = (idx: number) => {
    setExpandedIdx((prev) => (prev === idx ? null : idx));
  };

  const completedCount = events.filter(
    (e) => e.content && e.content.length > 0
  ).length;

  return (
    <div style={S.container}>
      <div style={S.header}>
        <div style={S.headerTitle}>
          📖 叙事时间线
          {events.length > 0 && (
            <span style={{ marginLeft: 8, opacity: 0.85, fontWeight: 400 }}>
              ({completedCount}/{events.length} 已完成)
            </span>
          )}
        </div>
        {events.length > 0 && (
          <button
            style={S.toggleBtn}
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            {isCollapsed ? "展开" : "收起"}
          </button>
        )}
      </div>

      {isCollapsed ? null : (
        <div style={S.body} ref={bodyRef}>
          {events.length === 0 ? (
            <div style={S.emptyState}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>📭</div>
              <div>暂无章节事件</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>
                开始创作后，章节事件将显示在这里
              </div>
            </div>
          ) : (
            <div style={S.timeline}>
              <div style={S.timelineLine} />
              {events.map((event, idx) => (
                <ChapterItem
                  key={idx}
                  event={event}
                  isExpanded={expandedIdx === idx}
                  onToggle={() => toggleExpand(idx)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
