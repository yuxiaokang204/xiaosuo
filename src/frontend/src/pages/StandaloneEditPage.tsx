/**
 * StandaloneEditPage — 独立编辑页
 * 支持原文输入、编辑指令、结果预览、流式输出
 */
import React, { useState } from "react";

export const StandaloneEditPage: React.FC = () => {
  const [content, setContent] = useState("");
  const [instructions, setInstructions] = useState("润色语言，使更精炼");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 快捷指令
  const quickInstructions = [
    { label: "润色语言", value: "润色语言，使更精炼" },
    { label: "丰富细节", value: "增加环境描写、心理活动和对话，使场景更生动" },
    { label: "减少AI感", value: "减少套话和重复句式，使用更自然的表达，避免模式化语言" },
    { label: "调整风格", value: "将文风调整为更沉稳内敛的风格" },
    { label: "翻译风格", value: "调整为中文网络文学的写作风格" },
  ];

  const edit = async () => {
    if (!content.trim()) return;
    setLoading(true);
    setError(null);
    setResult("");

    try {
      const r = await fetch("/api/create/edit-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, instructions }),
      });

      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: "HTTP " + r.status }));
        throw new Error(err.detail || err.error || "请求失败");
      }

      const reader = r.body?.getReader();
      if (!reader) throw new Error("无法读取流");

      const decoder = new TextDecoder();
      let fullResult = "";
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
                fullResult += data.token;
                setResult(fullResult);
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
            fullResult += data.token;
            setResult(fullResult);
          }
        } catch { /* ignore */ }
      }
    } catch (e: any) {
      setError(e.message || "编辑失败，请检查 LLM 配置");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>📝 独立编辑</h2>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        {/* 原文输入 */}
        <div style={{
          background: "var(--bg-primary)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: 20,
          display: "flex",
          flexDirection: "column",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ fontSize: 15, margin: 0 }}>原文</h3>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{content.length} 字</span>
          </div>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="textarea"
            style={{ flex: 1, minHeight: 300, fontFamily: "'Noto Serif SC', serif", lineHeight: 2 }}
            placeholder="在此粘贴需要编辑的章节内容..."
          />
        </div>

        {/* 编辑结果 */}
        <div style={{
          background: "var(--bg-primary)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: 20,
          display: "flex",
          flexDirection: "column",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ fontSize: 15, margin: 0 }}>
              编辑结果 {result && <span style={{ fontSize: 12, color: "var(--text-muted)" }}>({result.length} 字)</span>}
            </h3>
            {result && (
              <button
                onClick={() => navigator.clipboard.writeText(result)}
                className="btn btn-ghost btn-sm"
              >
                📋 复制
              </button>
            )}
          </div>
          <div style={{
            flex: 1, minHeight: 300, whiteSpace: "pre-wrap", lineHeight: 1.8, fontSize: 15,
            overflowY: "auto",
            fontFamily: "'Noto Serif SC', serif",
          }}>
            {result ? (
              result
            ) : error ? (
              <div style={{ color: "var(--danger)", fontSize: 13 }}>❌ {error}</div>
            ) : (
              <span style={{ color: "var(--text-muted)" }}>
                {loading ? "正在实时生成编辑结果..." : "编辑结果将显示在这里"}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 编辑指令区 */}
      <div style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: 12, padding: 24 }}>
        <h3 style={{ fontSize: 16, marginBottom: 12 }}>编辑指令</h3>

        {/* 快捷指令 */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
          {quickInstructions.map((qi) => (
            <button
              key={qi.label}
              onClick={() => setInstructions(qi.value)}
              className={`btn btn-sm ${instructions === qi.value ? "btn-primary" : "btn-secondary"}`}
            >
              {qi.label}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>自定义指令</label>
            <input
              type="text"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="input"
              placeholder="输入编辑指令，如：使对话更口语化"
            />
          </div>
          <button
            onClick={edit}
            disabled={loading || !content.trim()}
            className="btn btn-primary"
          >
            {loading ? "⏳ 编辑中..." : "✏️ 开始编辑"}
          </button>
        </div>
      </div>
    </div>
  );
};
