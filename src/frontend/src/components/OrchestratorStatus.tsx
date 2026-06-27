import React, { useState, useEffect, useRef } from "react";
import { api } from "../api";

// ──────────── 类型定义 ────────────

export interface AgentStatus {
  agent_id: string;
  agent_name: string;
  status: "idle" | "running" | "completed" | "error";
  progress: number;
  result?: any;
}

export interface StageProgress {
  stage: string;
  status: "pending" | "running" | "completed" | "error";
  progress: number;
  result?: any;
}

export interface OrchestratorState {
  novel_id: string;
  current_stage: string;
  stages: StageProgress[];
  active_agents: AgentStatus[];
  is_running: boolean;
}

interface OrchestratorStatusProps {
  novelId: string;
  autoRefresh?: boolean;
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
    background: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
    color: "#fff",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: 700,
  },
  statusIndicator: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 13,
    fontWeight: 600,
  },
  body: {
    padding: "20px 24px",
  },
  stageCard: {
    background: "#f9fafb",
    border: "1px solid #e5e7eb",
    borderRadius: 10,
    padding: 16,
    marginBottom: 12,
    transition: "all .2s",
  },
  stageCardRunning: {
    background: "#eff6ff",
    border: "2px solid #3b82f6",
    boxShadow: "0 2px 8px rgba(59,130,246,.15)",
  },
  stageCardCompleted: {
    background: "#f0fdf4",
    border: "2px solid #10b981",
  },
  stageCardError: {
    background: "#fef2f2",
    border: "2px solid #ef4444",
  },
  stageHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  stageName: {
    fontSize: 14,
    fontWeight: 700,
    color: "#1f2937",
  },
  progressBar: {
    height: 6,
    background: "#e5e7eb",
    borderRadius: 3,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: 3,
    transition: "width .3s ease",
  },
  agentList: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 12,
  },
  agentChip: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 12px",
    borderRadius: 999,
    fontSize: 12,
    fontWeight: 600,
  },
  eventLog: {
    maxHeight: 200,
    overflowY: "auto",
    background: "#1f2937",
    borderRadius: 8,
    padding: 12,
    fontFamily: "monospace",
    fontSize: 12,
    color: "#e5e7eb",
  },
  eventLine: {
    padding: "2px 0",
    borderBottom: "1px solid #374151",
  },
  badge: {
    display: "inline-flex",
    alignItems: "center",
    padding: "2px 8px",
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 600,
  },
  emptyState: {
    textAlign: "center",
    padding: "40px 20px",
    color: "#9ca3af",
    fontSize: 14,
  },
  refreshBtn: {
    background: "rgba(255,255,255,0.2)",
    border: "none",
    borderRadius: 6,
    color: "#fff",
    cursor: "pointer",
    padding: "4px 12px",
    fontSize: 12,
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    gap: 4,
  },
};

// ──────────── 状态徽章 ────────────

function StatusBadge({
  status,
  text,
}: {
  status: string;
  text: string;
}) {
  const colorMap: Record<string, { bg: string; fg: string }> = {
    pending: { bg: "#f3f4f6", fg: "#6b7280" },
    running: { bg: "#dbeafe", fg: "#1e40af" },
    completed: { bg: "#d1fae5", fg: "#065f46" },
    error: { bg: "#fee2e2", fg: "#991b1b" },
    idle: { bg: "#f3f4f6", fg: "#6b7280" },
  };

  const colors = colorMap[status] || colorMap.pending;

  return (
    <span
      style={{
        ...S.badge,
        background: colors.bg,
        color: colors.fg,
      }}
    >
      {status === "running" && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: colors.fg,
            display: "inline-block",
            animation: "pulse 1.5s infinite",
          }}
        />
      )}
      {text}
    </span>
  );
}

// ──────────── 阶段卡片 ────────────

function StageCard({ stage }: { stage: StageProgress }) {
  const progressColors: Record<string, string> = {
    pending: "#9ca3af",
    running: "#3b82f6",
    completed: "#10b981",
    error: "#ef4444",
  };

  const cardStyle = {
    ...S.stageCard,
    ...(stage.status === "running" ? S.stageCardRunning : {}),
    ...(stage.status === "completed" ? S.stageCardCompleted : {}),
    ...(stage.status === "error" ? S.stageCardError : {}),
  };

  const stageLabels: Record<string, string> = {
    planning: "📝 规划",
    worldbuilding: "🌍 世界观",
    characters: "👥 角色",
    style: "🎨 风格",
    outlining: "📋 大纲",
    drafting: " 正文",
    editing: "✏️ 精修",
    review: "🔍 审查",
    done: "✅ 完成",
  };

  return (
    <div style={cardStyle}>
      <div style={S.stageHeader}>
        <span style={S.stageName}>
          {stageLabels[stage.stage] || stage.stage}
        </span>
        <StatusBadge
          status={stage.status}
          text={
            stage.status === "pending"
              ? "等待中"
              : stage.status === "running"
              ? "进行中"
              : stage.status === "completed"
              ? "已完成"
              : "失败"
          }
        />
      </div>
      <div style={S.progressBar}>
        <div
          style={{
            ...S.progressFill,
            width: `${stage.progress}%`,
            background: progressColors[stage.status],
          }}
        />
      </div>
      <div
        style={{
          fontSize: 11,
          color: "#6b7280",
          marginTop: 4,
          textAlign: "right",
        }}
      >
        {stage.progress}%
      </div>
    </div>
  );
}

// ──────────── Agent 芯片 ────────────

function AgentChip({ agent }: { agent: AgentStatus }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    idle: { bg: "#f3f4f6", fg: "#6b7280" },
    running: { bg: "#dbeafe", fg: "#1e40af" },
    completed: { bg: "#d1fae5", fg: "#065f46" },
    error: { bg: "#fee2e2", fg: "#991b1b" },
  };

  const color = colors[agent.status] || colors.idle;

  return (
    <span
      style={{
        ...S.agentChip,
        background: color.bg,
        color: color.fg,
      }}
    >
      {agent.status === "running" && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: color.fg,
            display: "inline-block",
            animation: "pulse 1.5s infinite",
          }}
        />
      )}
      {agent.agent_name}
      {agent.progress > 0 && (
        <span style={{ opacity: 0.7 }}>
          ({agent.progress}%)
        </span>
      )}
    </span>
  );
}

// ──────────── SSE 事件日志 ────────────

function EventLog({ events }: { events: string[] }) {
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  if (events.length === 0) {
    return (
      <div
        style={{
          ...S.eventLog,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ color: "#6b7280" }}>等待事件...</span>
      </div>
    );
  }

  return (
    <div style={S.eventLog} ref={logRef}>
      {events.map((event, idx) => (
        <div key={idx} style={S.eventLine}>
          {event}
        </div>
      ))}
    </div>
  );
}

// ──────────── 主组件 ────────────

export const OrchestratorStatus: React.FC<OrchestratorStatusProps> = ({
  novelId,
  autoRefresh = true,
}) => {
  const [state, setState] = useState<OrchestratorState | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 获取编排状态
  const fetchStatus = async () => {
    if (!novelId) return;
    try {
      setLoading(true);
      const data = await api.orchestratorStatus(novelId);
      if (data) {
        setState(data);
        console.log("[OrchestratorStatus] 状态更新:", data);
      }
    } catch (e) {
      console.error("[OrchestratorStatus] 获取状态失败:", e);
    } finally {
      setLoading(false);
    }
  };

  // 自动刷新
  useEffect(() => {
    if (autoRefresh && novelId) {
      fetchStatus();
      refreshTimerRef.current = setInterval(fetchStatus, 3000);
    }

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }
    };
  }, [novelId, autoRefresh]);

  // 手动刷新
  const handleRefresh = () => {
    fetchStatus();
    setEvents((prev) => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] 手动刷新`,
    ]);
  };

  const isRunning = state?.is_running || false;

  return (
    <div style={S.container}>
      <div style={S.header}>
        <div style={S.headerTitle}>
          🔄 编排状态
          {novelId && (
            <span style={{ marginLeft: 8, opacity: 0.85, fontWeight: 400 }}>
              {novelId.slice(0, 8)}...
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {state?.is_running && (
            <div style={{ ...S.statusIndicator }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#fbbf24",
                  display: "inline-block",
                  animation: "pulse 1.5s infinite",
                }}
              />
              运行中
            </div>
          )}
          <button style={S.refreshBtn} onClick={handleRefresh} disabled={loading}>
            {loading ? "刷新中..." : "↻ 刷新"}
          </button>
        </div>
      </div>

      <div style={S.body}>
        {!novelId ? (
          <div style={S.emptyState}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>📭</div>
            <div>暂无编排任务</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>
              开始创作后，编排状态将显示在这里
            </div>
          </div>
        ) : !state ? (
          <div style={S.emptyState}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>⏳</div>
            <div>正在加载状态...</div>
          </div>
        ) : (
          <>
            {/* 阶段进度 */}
            <div style={{ marginBottom: 20 }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#6b7280",
                  marginBottom: 10,
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                }}
              >
                阶段进度
              </div>
              {state.stages.map((stage, idx) => (
                <StageCard key={idx} stage={stage} />
              ))}
            </div>

            {/* 活跃 Agent */}
            {state.active_agents.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "#6b7280",
                    marginBottom: 10,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  活跃 Agent
                </div>
                <div style={S.agentList}>
                  {state.active_agents.map((agent, idx) => (
                    <AgentChip key={idx} agent={agent} />
                  ))}
                </div>
              </div>
            )}

            {/* 当前阶段 */}
            <div style={{ marginBottom: 20 }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#6b7280",
                  marginBottom: 6,
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                }}
              >
                当前阶段
              </div>
              <div
                style={{
                  padding: "10px 16px",
                  background: isRunning ? "#eff6ff" : "#f9fafb",
                  border: isRunning
                    ? "2px solid #3b82f6"
                    : "1px solid #e5e7eb",
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: 600,
                  color: isRunning ? "#1e40af" : "#6b7280",
                }}
              >
                {state.current_stage || "无"}
              </div>
            </div>

            {/* SSE 事件日志 */}
            {isRunning && (
              <div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "#6b7280",
                    marginBottom: 6,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span>实时事件流</span>
                  <span
                    style={{
                      fontSize: 10,
                      color: "#10b981",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: "#10b981",
                        display: "inline-block",
                        animation: "pulse 1.5s infinite",
                      }}
                    />
                    实时更新
                  </span>
                </div>
                <EventLog events={events} />
              </div>
            )}
          </>
        )}
      </div>

      {/* 脉冲动画 */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
};
