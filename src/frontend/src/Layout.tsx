/**
 * Layout — 主布局外壳（侧边栏 + 顶部栏 + 内容区）
 */
import React, { useState } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface LayoutProps {
  children: React.ReactNode;
  currentPage: string;
  onNavigate: (page: string) => void;
  currentNovelTitle?: string;
}

export const Layout: React.FC<LayoutProps> = ({
  children, currentPage, onNavigate, currentNovelTitle,
}) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div style={{
      display: "flex", minHeight: "100vh",
      background: "var(--bg-secondary)",
    }}>
      <Sidebar
        currentPage={currentPage}
        onNavigate={onNavigate}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <div style={{
        flex: 1, display: "flex", flexDirection: "column",
        minWidth: 0,
      }}>
        <TopBar
          currentNovelTitle={currentNovelTitle}
        />
        <main style={{
          flex: 1, padding: 24,
          overflowY: "auto",
          height: `calc(100vh - 56px)`,
        }}>
          {children}
        </main>
      </div>
    </div>
  );
};
