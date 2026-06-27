/**
 * LLMConfigPage — LLM 配置页（重构自 LLMConfigPanel.tsx）
 */
import React, { useState, useEffect } from "react";

export const LLMConfigPage: React.FC = () => {
  const [providers, setProviders] = useState<any[]>([]);
  const [config, setConfig] = useState<any>(null);
  const [configs, setConfigs] = useState<any[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState("");
  const [savingConfig, setSavingConfig] = useState("");

  useEffect(() => {
    Promise.all([
      fetch("/api/llm/providers").then((r) => r.json()).catch(() => ({ providers: [] })),
      fetch("/api/llm/config").then((r) => r.json()).catch(() => null),
      fetch("/api/llm/configs").then((r) => r.json()).catch(() => ({ configs: [] })),
    ]).then(([p, c, cs]) => {
      setProviders(p.providers || []);
      setConfig(c);
      setConfigs(cs.configs || []);
    });
  }, []);

  const saveConfig = async () => {
    setSavingConfig("save");
    try {
      const body: any = { provider: selectedProvider, model, api_base: apiBase };
      if (apiKey) body.api_key = apiKey;
      await fetch("/api/llm/config", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setTestResult("✅ 配置已保存");
      setSavingConfig("");
      // 刷新配置列表和当前配置
      const [c, cs] = await Promise.all([
        fetch("/api/llm/config").then((r) => r.json()).catch(() => null),
        fetch("/api/llm/configs").then((r) => r.json()).catch(() => ({ configs: [] })),
      ]);
      setConfig(c);
      setConfigs(cs.configs || []);
    } catch (e: any) {
      setTestResult(`❌ ${e.message}`);
      setSavingConfig("");
    }
  };

  const testLLM = async () => {
    setTesting(true);
    setTestResult("⏳ 测试中...");
    try {
      const r = await fetch("/api/llm/test", { method: "POST" });
      const data = await r.json();
      setTestResult(data.success ? `✅ ${data.message || "测试成功"}` : `❌ ${data.error || "测试失败"}`);
    } catch (e: any) {
      setTestResult(`❌ ${e.message}`);
    } finally {
      setTesting(false);
    }
  };

  const handleProviderChange = (pid: string) => {
    setSelectedProvider(pid);
    const p = providers.find((pp) => pp.id === pid);
    if (p?.models?.length) setModel(p.models[0]);
    if (p?.api_base) setApiBase(p.api_base);
    setApiKey("");
  };

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>⚙️ LLM 配置</h2>

      {/* 当前配置 */}
      <div style={{
        background: "var(--bg-primary)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: 24,
        marginBottom: 24,
      }}>
        <h3 style={{ fontSize: 16, marginBottom: 16 }}>当前配置</h3>
        {config ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
            <div><span style={{ fontSize: 12, color: "var(--text-muted)" }}>Provider</span><div style={{ fontWeight: 600 }}>{config.provider || config.provider_type || "-"}</div></div>
            <div><span style={{ fontSize: 12, color: "var(--text-muted)" }}>模型</span><div style={{ fontWeight: 600 }}>{config.model || "-"}</div></div>
            <div><span style={{ fontSize: 12, color: "var(--text-muted)" }}>API Key</span><div style={{ fontWeight: 600 }}>{config.has_api_key ? "✅ 已配置" : "❌ 未配置"}</div></div>
          </div>
        ) : (
          <span style={{ color: "var(--text-muted)" }}>无配置</span>
        )}
      </div>

      {/* 切换 Provider */}
      <div style={{
        background: "var(--bg-primary)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: 24,
        marginBottom: 24,
      }}>
        <h3 style={{ fontSize: 16, marginBottom: 16 }}>切换 Provider</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
          <div>
            <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>Provider</label>
            <select value={selectedProvider || (config?.provider_type || "")} onChange={(e) => handleProviderChange(e.target.value)} className="select">
              <option value="">选择 Provider...</option>
              {providers.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>模型</label>
            <input type="text" value={model} onChange={(e) => setModel(e.target.value)} className="input" placeholder="自动填充" />
          </div>
          <div>
            <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>API Base（可选）</label>
            <input type="text" value={apiBase} onChange={(e) => setApiBase(e.target.value)} className="input" />
          </div>
          <div>
            <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>API Key</label>
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} className="input" placeholder={providers.find((p) => p.id === (selectedProvider || config?.provider_type))?.needs_api_key ? "需要 API Key" : "不需要"} />
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button onClick={saveConfig} disabled={savingConfig === "save"} className="btn btn-primary">💾 保存配置</button>
          <button onClick={testLLM} disabled={testing} className="btn btn-secondary">🧪 测试</button>
        </div>
        {testResult && <div style={{ marginTop: 12, padding: 10, background: "var(--bg-tertiary)", borderRadius: 8, fontSize: 13 }}>{testResult}</div>}
      </div>

      {/* 已保存配置列表 */}
      <div style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: 12, padding: 24 }}>
        <h3 style={{ fontSize: 16, marginBottom: 16 }}>已保存的配置</h3>
        {configs.length === 0 ? (
          <span style={{ color: "var(--text-muted)" }}>暂无保存的配置</span>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {configs.map((c: any) => (
              <div key={c.id} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: 12, background: "var(--bg-secondary)", borderRadius: 8,
                border: c.is_default ? "2px solid var(--accent)" : "1px solid var(--border-subtle)",
              }}>
                <div>
                  <span style={{ fontWeight: 600 }}>{c.name}</span>
                  <span style={{ marginLeft: 8, fontSize: 12, color: "var(--text-muted)" }}>
                    {c.provider} · {c.model}
                  </span>
                  {c.is_default && <span className="badge badge-accent" style={{ marginLeft: 8 }}>默认</span>}
                </div>
                <div style={{ display: "flex", gap: 4 }}>
                  <button onClick={async () => {
                    try { await fetch(`/api/llm/configs/${c.id}/set-default`, { method: "POST" }); window.location.reload(); } catch {}
                  }} className="btn btn-ghost btn-sm">设为默认</button>
                  <button onClick={async () => {
                    if (!confirm("确定删除？")) return;
                    try { await fetch(`/api/llm/configs/${c.id}`, { method: "DELETE" }); window.location.reload(); } catch {}
                  }} className="btn btn-ghost btn-sm" style={{ color: "var(--danger)" }}>删除</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
