/**
 * TopBar — 顶部导航栏
 */
import React from "react";

interface TopBarProps {
  currentNovelTitle?: string;
  collapsed?: boolean;
  onToggleSidebar?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ currentNovelTitle }) => {
  // 获取主题（从 document attribute 读取）
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  const toggleTheme = () => {
    const current = document.documentElement.getAttribute("data-theme");
    document.documentElement.setAttribute("data-theme", current === "dark" ? "light" : "dark");
    localStorage.setItem("novel-agent-theme", current === "dark" ? "light" : "dark");
  };

  return (
    <header style={{
      height: 56,
      padding: "0 24px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      borderBottom: "1px solid var(--border)",
      background: "var(--bg-primary)",
      flexShrink: 0,
      position: "sticky",
      top: 0,
      zIndex: 50,
    }}>
      {/* 左侧：当前小说标题或页面标题 */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          fontSize: 13, color: "var(--text-muted)",
        }}>
          <span>📖</span>
          <span style={{
            fontWeight: 600, color: "var(--text-primary)",
            maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {currentNovelTitle || "未选择小说"}
          </span>
        </div>
      </div>

      {/* 右侧：操作按钮 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {/* 主题切换 */}
        <button
          onClick={toggleTheme}
          style={{
            background: "none", border: "none", cursor: "pointer",
            fontSize: 18, padding: 6, borderRadius: 6,
            color: "var(--text-secondary)",
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "background 150ms ease",
          }}
          title={isDark ? "切换到亮色主题" : "切换到暗色主题"}
          onMouseEnter={(e) => {
            (e.target as HTMLElement).style.background = "var(--bg-tertiary)";
          }}
          onMouseLeave={(e) => {
            (e.target as HTMLElement).style.background = "transparent";
          }}
        >
          {isDark ? "☀️" : "🌙"}
        </button>

        {/* 健康状态 */}
        <HealthIndicator />
      </div>
    </header>
  );
};

/**
 * HealthIndicator — 后端健康状态指示器
 */
const HealthIndicator: React.FC = () => {
  const [status, setStatus] = React.useState<"ok" | "error" | null>(null);
  const [agents, setAgents] = React.useState(0);

  React.useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => {
        setStatus(d.status === "healthy" ? "ok" : null);
        setAgents(d.agents_registered || 0);
      })
      .catch(() => setStatus("error"));
  }, []);

  if (status === null) return null;

  const color = status === "ok" ? "var(--success)" : "var(--danger)";
  const text = status === "ok" ? "已连接" : "离线";

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 6,
      fontSize: 12, color, padding: "4px 10px",
      background: status === "ok" ? "var(--success-light)" : "var(--danger-light)",
      borderRadius: 999, fontWeight: 600,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: "50%",
        background: color, display: "inline-block",
      }} />
      {text} · {agents} agents
    </div>
  );
};
