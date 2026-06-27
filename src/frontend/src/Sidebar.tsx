/**
 * Sidebar — 侧边栏导航（v4.1 分组版）
 */
import React, { useState } from "react";

interface NavItem {
  id: string;
  label: string;
  icon: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "创作区",
    items: [
      { id: "overview", label: "系统总览", icon: "📊" },
      { id: "orchestrator", label: "全流程编排", icon: "🚀" },
      { id: "novels", label: "小说管理", icon: "📚" },
      { id: "read", label: "阅读模式", icon: "📖" },
    ],
  },
  {
    label: "管理区",
    items: [
      { id: "characters", label: "角色管理", icon: "👥" },
      { id: "world", label: "世界观设定", icon: "🌍" },
      { id: "prompts", label: "Prompt 管理", icon: "💬" },
      { id: "llm", label: "LLM 配置", icon: "⚙️" },
    ],
  },
  {
    label: "工具区",
    items: [
      { id: "draft", label: "独立草稿", icon: "✍️" },
      { id: "edit", label: "独立编辑", icon: "📝" },
      { id: "search", label: "语义搜索", icon: "🔍" },
      { id: "learning", label: "学习引擎", icon: "🧠" },
      { id: "dashboard", label: "仪表盘", icon: "📈" },
    ],
  },
];

interface SidebarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
  collapsed: boolean;
  onToggle: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPage, onNavigate, collapsed, onToggle,
}) => {
  // 默认展开创作区，其他折叠
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({
    "管理区": true,
    "工具区": true,
  });

  const toggleGroup = (label: string) => {
    setCollapsedGroups((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  return (
    <aside style={{
      width: collapsed ? 64 : 260,
      minWidth: collapsed ? 64 : 260,
      height: "100vh",
      position: "sticky",
      top: 0,
      background: "var(--bg-primary)",
      borderRight: "1px solid var(--border)",
      display: "flex",
      flexDirection: "column",
      transition: "all 250ms ease",
      zIndex: 100,
      overflow: "hidden",
    }}>
      {/* 品牌头部 */}
      <div style={{
        padding: collapsed ? "16px 0" : "16px 20px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: collapsed ? "center" : "space-between",
        height: 56,
        flexShrink: 0,
      }}>
        {!collapsed && (
          <span style={{
            fontSize: 16, fontWeight: 700, color: "var(--accent)",
            whiteSpace: "nowrap",
          }}>
            ✨ 小说Agent
          </span>
        )}
        <button
          onClick={onToggle}
          style={{
            background: "none", border: "none", cursor: "pointer",
            fontSize: 18, padding: 4, color: "var(--text-secondary)",
            display: "flex", alignItems: "center", justifyContent: "center",
            borderRadius: 6,
          }}
          title={collapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          {collapsed ? "☰" : "◀"}
        </button>
      </div>

      {/* 导航列表 */}
      <nav style={{
        flex: 1, overflowY: "auto", padding: collapsed ? "8px 0" : "8px 10px",
      }}>
        {NAV_GROUPS.map((group) => {
          const isGroupCollapsed = collapsedGroups[group.label] ?? false;
          return (
            <div key={group.label} style={{ marginBottom: 4 }}>
              {/* 分组标题 */}
              {!collapsed && (
                <button
                  onClick={() => toggleGroup(group.label)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    width: "100%",
                    padding: "6px 12px 4px",
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    fontSize: 11,
                    fontWeight: 700,
                    color: "var(--text-muted)",
                    textTransform: "uppercase",
                    letterSpacing: 1,
                  }}
                >
                  <span style={{
                    fontSize: 10,
                    transition: "transform 200ms",
                    transform: isGroupCollapsed ? "rotate(-90deg)" : "rotate(0deg)",
                  }}>
                    ▼
                  </span>
                  {group.label}
                </button>
              )}
              {/* 分组项 */}
              <div style={{
                maxHeight: collapsed || isGroupCollapsed ? 0 : 500,
                overflow: "hidden",
                transition: "max-height 300ms ease",
              }}>
                {group.items.map((item) => {
                  const isActive = currentPage === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => onNavigate(item.id)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        width: "100%",
                        padding: collapsed ? "10px 0" : "10px 12px",
                        margin: "2px 0",
                        border: "none",
                        borderRadius: 8,
                        cursor: "pointer",
                        fontSize: 14,
                        fontWeight: isActive ? 600 : 400,
                        color: isActive ? "var(--accent)" : "var(--text-secondary)",
                        background: isActive ? "var(--accent-light)" : "transparent",
                        justifyContent: collapsed ? "center" : "flex-start",
                        transition: "all 150ms ease",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                      }}
                      title={collapsed ? item.label : undefined}
                    >
                      <span style={{ fontSize: 18, flexShrink: 0 }}>{item.icon}</span>
                      {!collapsed && (
                        <span style={{ flex: 1, textAlign: "left" }}>{item.label}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      {/* 底部信息 */}
      <div style={{
        padding: collapsed ? "12px 0" : "12px 20px",
        borderTop: "1px solid var(--border)",
        fontSize: 11,
        color: "var(--text-muted)",
        textAlign: "center",
        flexShrink: 0,
      }}>
        {!collapsed && (
          <span>
            FastAPI + React + TypeScript
          </span>
        )}
      </div>
    </aside>
  );
};
