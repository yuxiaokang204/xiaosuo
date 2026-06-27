/**
 * LoadingSpinner — 可复用加载动画
 */
import React from "react";

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  text?: string;
  fullScreen?: boolean;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = "md",
  text,
  fullScreen,
}) => {
  const sizeClass = size === "sm" ? "spinner-sm" : size === "lg" ? "spinner-lg" : "";

  if (fullScreen) {
    return (
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", minHeight: "400px", gap: 16,
      }}>
        <div className={`spinner ${sizeClass}`} />
        {text && <span style={{ color: "var(--text-secondary)", fontSize: 14 }}>{text}</span>}
      </div>
    );
  }

  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 8,
    }}>
      <div className={`spinner ${sizeClass}`} />
      {text && <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>{text}</span>}
    </div>
  );
};
