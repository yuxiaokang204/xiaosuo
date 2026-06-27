import { useState, useEffect } from "react";
import { api } from "../api";

interface LLMConfig {
  id: string;
  name: string;
  provider: string;
  model: string;
  api_base: string;
  has_api_key: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

const PROVIDERS = [
  { value: "custom_openai", label: "自定义 OpenAI", desc: "通用OpenAI兼容接口（中国移动MAAS等）" },
  { value: "openai", label: "OpenAI", desc: "api.openai.com" },
  { value: "deepseek", label: "DeepSeek", desc: "api.deepseek.com" },
  { value: "ollama", label: "Ollama（本地）", desc: "http://localhost:11434" },
  { value: "mock", label: "Mock（测试）", desc: "无需API密钥，返回模拟数据" },
];

export default function LLMConfigPanel() {
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<LLMConfig | null>(null);

  // 表单
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("custom_openai");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [apiBase, setApiBase] = useState("");

  const loadConfigs = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("/api/llm/configs");
      setConfigs(data.configs || []);
    } catch (e: any) {
      setError("加载失败: " + (e?.message || "未知错误"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadConfigs(); }, []);

  const openForm = (cfg?: LLMConfig) => {
    if (cfg) {
      setEditing(cfg);
      setName(cfg.name);
      setProvider(cfg.provider);
      setApiKey(""); // 不显示已有API密钥
      setModel(cfg.model);
      setApiBase(cfg.api_base);
    } else {
      setEditing(null);
      setName("");
      setProvider("custom_openai");
      setApiKey("");
      setModel("");
      setApiBase("");
    }
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!name.trim()) { setError("请输入配置名称"); return; }
    if (provider !== "mock" && provider !== "ollama" && !apiKey.trim() && !editing?.has_api_key) {
      setError("请输入API密钥"); return;
    }
    setSaving(true);
    setError("");
    try {
      const body = { name: name.trim(), provider, api_key: apiKey.trim(), model: model.trim(), api_base: apiBase.trim() };
      if (editing) {
        await api.put(`/api/llm/configs/${editing.id}`, body);
      } else {
        await api.post("/api/llm/configs", body);
      }
      setShowForm(false);
      await loadConfigs();
    } catch (e: any) {
      setError("保存失败: " + (e?.message || "未知错误"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (cfg: LLMConfig) => {
    if (!confirm(`确定删除配置「${cfg.name}」？`)) return;
    try {
      await api.delete(`/api/llm/configs/${cfg.id}`);
      await loadConfigs();
    } catch (e: any) {
      setError("删除失败: " + (e?.message || "未知错误"));
    }
  };

  const handleSetDefault = async (cfg: LLMConfig) => {
    try {
      await api.post(`/api/llm/configs/${cfg.id}/set-default`);
      await loadConfigs();
    } catch (e: any) {
      setError("设置默认失败: " + (e?.message || "未知错误"));
    }
  };

  const handleTest = async (cfg: LLMConfig) => {
    setError("");
    try {
      const res = await api.post("/api/create/world-auto", {
        name: "测试",
        category: "科幻",
        config_id: cfg.id,
      });
      if (res.success) {
        alert(`✅ 配置「${cfg.name}」连接成功！\n\nAI返回的描述：${(res.data?.description || "").slice(0, 100)}...`);
      } else {
        const errMsg = res.error || res.detail || res.message || "未知错误";
        setError(`测试失败: ${errMsg}`);
      }
    } catch (e: any) {
      setError(`测试失败: ${e?.message || "连接异常"}`);
    }
  };

  const S: Record<string, React.CSSProperties> = {
    card: { background: "#fff", borderRadius: 8, padding: "16px 18px", border: "1px solid #e5e7eb", marginBottom: 10 },
    title: { fontWeight: 700, fontSize: 15, color: "#1f2937" },
    subtitle: { fontSize: 12, color: "#6b7280", marginTop: 2 },
    badge: { display: "inline-block", padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600 },
    chip: { display: "inline-block", padding: "3px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600, background: "#e5e7eb", color: "#4b5563" },
    btn: { padding: "6px 14px", borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: "pointer", border: "none", color: "#fff" },
    btnSm: { padding: "4px 10px", borderRadius: 5, fontSize: 12, cursor: "pointer", border: "none" },
    input: { width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14, color: "#1f2937", outline: "none", boxSizing: "border-box" as const },
    label: { fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 4, display: "block" },
    select: { width: "100%", padding: "8px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14, outline: "none", background: "#fff" },
  };

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 18, color: "#111827" }}>LLM 模型管理</h3>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6b7280" }}>配置多个AI模型，AI生成内容时可自由选择</p>
        </div>
        <button onClick={() => openForm()} style={{ ...S.btn, background: "#6366f1" }}>+ 添加配置</button>
      </div>

      {error && (
        <div style={{ background: "#fef2f2", borderRadius: 6, padding: "10px 14px", color: "#dc2626", fontSize: 13, marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{error}</span>
          <button onClick={() => setError("")} style={{ background: "none", border: "none", color: "#dc2626", cursor: "pointer", fontSize: 16 }}>×</button>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: 30, color: "#9ca3af" }}>加载中...</div>
      ) : configs.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, background: "#f9fafb", borderRadius: 8, border: "1px dashed #d1d5db" }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🤖</div>
          <div style={{ fontSize: 14, color: "#6b7280", marginBottom: 12 }}>还没有配置任何AI模型</div>
          <button onClick={() => openForm()} style={{ ...S.btn, background: "#6366f1" }}>添加第一个配置</button>
        </div>
      ) : (
        configs.map(cfg => (
          <div key={cfg.id} style={{ ...S.card, borderColor: cfg.is_default ? "#6366f1" : "#e5e7eb", borderWidth: cfg.is_default ? 2 : 1 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={S.title}>{cfg.name}</span>
                  {cfg.is_default && <span style={{ ...S.badge, background: "#eef2ff", color: "#4f46e5" }}>默认</span>}
                  <span style={S.chip}>{PROVIDERS.find(p => p.value === cfg.provider)?.label || cfg.provider}</span>
                  {cfg.has_api_key && <span style={{ fontSize: 10, color: "#10b981" }}>✓ 已配置密钥</span>}
                </div>
                <div style={S.subtitle}>
                  {cfg.model && <span>模型: {cfg.model} · </span>}
                  {cfg.api_base && <span>API: {cfg.api_base} · </span>}
                  创建于 {cfg.created_at?.slice(0, 10) || "未知"}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                <button onClick={() => handleTest(cfg)} style={{ ...S.btnSm, background: "#f59e0b", color: "#fff" }}>测试</button>
                {!cfg.is_default && (
                  <button onClick={() => handleSetDefault(cfg)} style={{ ...S.btnSm, background: "#6366f1", color: "#fff" }}>设为默认</button>
                )}
                <button onClick={() => openForm(cfg)} style={{ ...S.btnSm, background: "#e5e7eb", color: "#374151" }}>编辑</button>
                <button onClick={() => handleDelete(cfg)} style={{ ...S.btnSm, background: "#fee2e2", color: "#dc2626" }}>删除</button>
              </div>
            </div>
          </div>
        ))
      )}

      {/* 添加/编辑表单 Modal */}
      {showForm && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }} onClick={() => setShowForm(false)}>
          <div style={{ background: "#fff", borderRadius: 12, padding: 24, width: 480, maxWidth: "90vw", maxHeight: "85vh", overflow: "auto" }} onClick={e => e.stopPropagation()}>
            <h4 style={{ margin: "0 0 16px", fontSize: 16, color: "#111827" }}>{editing ? "编辑配置" : "添加LLM配置"}</h4>

            <div style={{ marginBottom: 12 }}>
              <label style={S.label}>配置名称 *</label>
              <input style={S.input} placeholder="如：中国移动MAAS" value={name} onChange={e => setName(e.target.value)} />
            </div>

            <div style={{ marginBottom: 12 }}>
              <label style={S.label}>服务商 *</label>
              <select style={S.select} value={provider} onChange={e => setProvider(e.target.value)}>
                {PROVIDERS.map(p => (
                  <option key={p.value} value={p.value}>{p.label} — {p.desc}</option>
                ))}
              </select>
            </div>

            {provider === "custom_openai" && (
              <div style={{ marginBottom: 12 }}>
                <label style={S.label}>API 地址 *</label>
                <input style={S.input} placeholder="https://maas.gd.chinamobile.com:36007/ai/uifm/open/v1" value={apiBase} onChange={e => setApiBase(e.target.value)} />
              </div>
            )}

            <div style={{ marginBottom: 12 }}>
              <label style={S.label}>模型名称</label>
              <input style={S.input} placeholder="如：minimax-m25 / gpt-4o / qwen36-35b" value={model} onChange={e => setModel(e.target.value)} />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={S.label}>API 密钥 {provider !== "mock" && provider !== "ollama" ? "*" : "(可选)"}</label>
              <input style={S.input} type="password" placeholder={editing?.has_api_key ? "留空则不修改已有密钥" : "sk-..."} value={apiKey} onChange={e => setApiKey(e.target.value)} />
            </div>

            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button onClick={() => setShowForm(false)} style={{ ...S.btn, background: "#e5e7eb", color: "#374151" }}>取消</button>
              <button onClick={handleSave} disabled={saving} style={{ ...S.btn, background: "#6366f1", opacity: saving ? 0.6 : 1 }}>
                {saving ? "保存中..." : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}