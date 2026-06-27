/**
 * MarkdownPreview — Markdown 渲染组件
 */
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownPreviewProps {
  content: string;
  className?: string;
}

export const MarkdownPreview: React.FC<MarkdownPreviewProps> = ({ content, className }) => {
  if (!content) {
    return (
      <div style={{
        padding: 24, textAlign: "center", color: "var(--text-muted)",
        background: "var(--bg-tertiary)", borderRadius: 12,
      }}>
        暂无内容
      </div>
    );
  }

  return (
    <div className={`markdown-content ${className || ""}`} style={{ padding: 20 }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );
};
