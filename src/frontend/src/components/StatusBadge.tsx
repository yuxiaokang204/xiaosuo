/**
 * StatusBadge — 状态指示器组件
 */
import React from "react";

interface StatusBadgeProps {
  status: "success" | "warning" | "danger" | "info" | "accent" | "default";
  text: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, text }) => {
  const badgeClass = status === "default" ? "badge badge-accent" : `badge badge-${status}`;

  return <span className={badgeClass}>{text}</span>;
};
