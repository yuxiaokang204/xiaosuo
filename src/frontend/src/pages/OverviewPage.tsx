/**
 * OverviewPage — 系统总览页
 */
import React, { useState, useEffect } from "react";

interface HealthInfo { status: string; agents_registered: number; llm_provider?: string; }
interface AgentInfo { name: string; description?: string; capabilities?: string[]; }

export const OverviewPage: React.FC = () => {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [testResult, setTestResult] = useState<string>("（点击下方按钮测试 API）");
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch("/api/health").then((r) => r.json()).catch(() => null),
      fetch("/api/agents").then((r) => r.json()).catch(() => ({ agents: [] })),
      fetch("/api/llm/providers").then((r) => r.json()).catch(() => ({ providers: [] })),
    ]).then(([h, a, p]) => {
      setHealth(h);
      const raw = a?.agents;
      setAgents(Array.isArray(raw) ? raw : Object.values(raw || {}));
      const rawP = p?.providers;
      setProviders(Array.isArray(rawP) ? rawP : Object.values(rawP || {}));
    });
  }, []);

  const testAPI = async (path: string, method = "POST", body: any = {}) => {
    setTesting(true);
    setTestResult("⏳ 请求中...");
    try {
      const r = await fetch(path, {
        method, headers: { "Content-Type": "application/json" },
        body: method === "POST" ? JSON.stringify(body) : undefined,
      });
      const text = await r.text();
      let d: any;
      try { d = JSON.parse(text); } catch { d = { raw: text }; }
      setTestResult(JSON.stringify(d, null, 2).slice(0, 1000));
    } catch (e: any) {
      setTestResult(`❌ ${e.message}`);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 8, fontSize: 22 }}>📊 系统总览</h2>

      {/* 快速开始引导 */}
      <div style={{
        background: "linear-gradient(135deg, var(--accent-light), var(--info-light))",
        border: "1px solid var(--accent)",
        borderRadius: 12,
        padding: "16px 20px",
        marginBottom: 20,
        fontSize: 13,
        lineHeight: 1.8,
        color: "var(--text-primary)",
      }}>
        <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 14 }}>🚀 快速开始</div>
        <div>1. 前往 <a href="#" onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "llmconfig" } })); }} style={{ color: "var(--accent)", fontWeight: 600 }}>LLM 配置</a> 设置 API Key 和模型</div>
        <div>2. 前往 <a href="#" onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "characters" } })); }} style={{ color: "var(--accent)", fontWeight: 600 }}>角色管理</a> 创建预设角色</div>
        <div>3. 前往 <a href="#" onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "world" } })); }} style={{ color: "var(--accent)", fontWeight: 600 }}>世界观设定</a> 创建预设世界观</div>
        <div>4. 前往 <a href="#" onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "orchestrator" } })); }} style={{ color: "var(--accent)", fontWeight: 600 }}>编排创作</a> 开始全流程创作</div>
      </div>

      {/* 状态卡片 */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
        gap: 16,
        marginBottom: 24,
      }}>
        {[
          { label: "Agent 数量", value: health?.agents_registered ?? 0, color: "var(--accent)", bg: "var(--accent-light)" },
          { label: "LLM Provider", value: health?.llm_provider || "mock", color: "var(--success)", bg: "var(--success-light)" },
          { label: "支持模型数", value: providers.length, color: "var(--warning)", bg: "var(--warning-light)" },
          { label: "后端状态", value: health ? "✅ 已连接" : "⚠️ 离线", color: health ? "var(--success)" : "var(--danger)", bg: health ? "var(--success-light)" : "var(--danger-light)" },
        ].map((card, i) => (
          <div key={i} style={{
            padding: 20,
            background: "var(--bg-primary)",
            border: "1px solid var(--border)",
            borderRadius: 12,
            boxShadow: "var(--shadow-sm)",
          }}>
            <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 8 }}>{card.label}</div>
            <div style={{
              fontSize: 24, fontWeight: 700, color: card.color,
              background: card.bg, padding: 8, borderRadius: 8, textAlign: "center",
            }}>
              {card.value}
            </div>
          </div>
        ))}
      </div>

      {/* Agent 列表 */}
      <div style={{
        background: "var(--bg-primary)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: 20,
        marginBottom: 24,
        boxShadow: "var(--shadow-sm)",
      }}>
        <h3 style={{ fontSize: 16, marginBottom: 12 }}>🤖 已注册 Agent</h3>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {agents.map((a: any, i: number) => (
            <span key={i} style={{
              padding: "6px 14px",
              background: "var(--bg-tertiary)",
              borderRadius: 999,
              fontSize: 13,
              color: "var(--text-primary)",
              display: "flex", alignItems: "center", gap: 6,
            }}>
              <span style={{ fontWeight: 600 }}>{a.name || "Unknown"}</span>
              <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
                · {(a.description || "").slice(0, 30)}
              </span>
            </span>
          ))}
          {agents.length === 0 && (
            <span style={{ color: "var(--text-muted)", fontSize: 13 }}>暂无 Agent 数据</span>
          )}
        </div>
      </div>

      {/* 快速测试 */}
      <div style={{
        background: "var(--bg-primary)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: 20,
        boxShadow: "var(--shadow-sm)",
      }}>
        <h3 style={{ fontSize: 16, marginBottom: 12 }}>🧪 快速测试</h3>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
          {[
            { label: "生成大纲", path: "/api/create/outline", body: { theme: "穿越修真", tone: "史诗", chapter_count: 5 } },
            { label: "生成世界观", path: "/api/create/world", body: { theme: "青云界" } },
            { label: "生成角色", path: "/api/create/character", body: { role: "主角" } },
            { label: "生成剧情", path: "/api/create/plot", body: { summaries: "主角穿越到异世" } },
          ].map((btn) => (
            <button
              key={btn.label}
              onClick={() => testAPI(btn.path, "POST", btn.body)}
              disabled={testing}
              style={{
                padding: "8px 16px",
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                cursor: testing ? "not-allowed" : "pointer",
                fontSize: 13,
                fontWeight: 600,
                opacity: testing ? 0.5 : 1,
              }}
            >
              {btn.label}
            </button>
          ))}
        </div>
        <pre style={{
          padding: 16,
          background: "var(--bg-tertiary)",
          borderRadius: 8,
          fontSize: 13,
          lineHeight: 1.6,
          maxHeight: 300,
          overflow: "auto",
          color: "var(--text-primary)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
        }}>
          {testResult}
        </pre>
      </div>
    </div>
  );
};
