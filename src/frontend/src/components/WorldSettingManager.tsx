import { useState, useEffect, useCallback } from "react";
import { api } from "../api";

interface WorldSetting {
  id: string;
  name: string;
  category: string;
  description: string;
  rules: string[];
  history: string[];
  novel_id?: string;
  created_at?: string;
  updated_at?: string;
}

const emptyWorld: WorldSetting = {
  id: "", name: "", category: "", description: "",
  rules: [], history: [],
};

const CATEGORY_OPTIONS = ["奇幻", "科幻", "武侠", "仙侠", "都市", "历史", "悬疑", "恐怖", "末世", "二次元", "其他"];

export default function WorldSettingManager() {
  const [worlds, setWorlds] = useState<WorldSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<WorldSetting | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [error, setError] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [llmConfigs, setLlmConfigs] = useState<any[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState("");

  const loadWorlds = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getPresets();
      const items = (data.world_settings || []).map((w: any) => ({
        id: w.id || "",
        name: w.name || "",
        category: w.category || "",
        description: w.description || "",
        rules: w.rules || [],
        history: w.history || [],
        novel_id: w.novel_id,
        created_at: w.created_at,
        updated_at: w.updated_at,
      }));
      setWorlds(items);
    } catch (e) {
      console.error("加载世界观失败:", e);
    }
    setLoading(false);

    // 加载LLM配置
    try {
      const llmData = await api.get("/api/llm/configs");
      setLlmConfigs(llmData.configs || []);
      const def = (llmData.configs || []).find((c: any) => c.is_default);
      setSelectedConfigId(def?.id || ((llmData.configs || [])[0]?.id || ""));
    } catch { /* 忽略 */ }
  }, []);

  useEffect(() => {
    loadWorlds();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAdd = () => {
    setEditing({ ...emptyWorld });
    setIsNew(true);
    setShowForm(true);
    setError("");
  };

  const handleEdit = (world: WorldSetting) => {
    setEditing({ ...world });
    setIsNew(false);
    setShowForm(true);
    setError("");
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("确定删除此世界观？此操作不可撤销。")) return;
    try {
      await api.delete(`/api/settings/world/${id}`);
      setWorlds((prev) => prev.filter((w) => w.id !== id));
    } catch (e) {
      console.error("删除世界观失败:", e);
      setError("删除失败，请重试");
    }
  };

  // 多选切换
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // 全选/取消全选
  const toggleSelectAll = () => {
    if (selectedIds.size === worlds.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(worlds.map((w) => w.id)));
    }
  };

  // 批量删除
  const batchDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`确定删除选中的 ${selectedIds.size} 个世界观？此操作不可恢复。`)) return;
    try {
      await fetch("/api/settings/world/batch-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([...selectedIds]),
      });
      setWorlds((prev) => prev.filter((w) => !selectedIds.has(w.id)));
      setSelectedIds(new Set());
    } catch (e: any) {
      console.error("批量删除世界观失败:", e);
      setError("批量删除失败，请重试");
    }
  };

  // ── AI 自动生成世界观详情 ──
  const handleAiGen = async () => {
    if (!editing) return;
    const name = editing.name.trim();
    if (!name) {
      setError("请先输入世界观名称");
      return;
    }
    if (!editing.category) {
      setError("请先选择世界观类型");
      return;
    }
    setAiGenerating(true);
    setError("");
    try {
      const res = await api.post("/api/create/world-auto", {
        name: editing.name,
        category: editing.category,
        config_id: selectedConfigId,
      });
      if (!res || !res.data) {
        const errMsg = res?.error || res?.detail || res?.message || "AI生成失败，请确认LLM已配置";
        setError(errMsg);
        setAiGenerating(false);
        return;
      }
      const data = res.data;
      setEditing({
        ...editing,
        description: data.description || editing.description,
        rules: data.rules || editing.rules,
        history: data.history || editing.history,
      });
    } catch (e: any) {
      setError(e?.message || "AI生成失败，请重试");
    }
    setAiGenerating(false);
  };

  const handleSave = async () => {
    if (!editing) return;
    const name = editing.name.trim();
    if (!name) {
      setError("世界观名称不能为空");
      return;
    }

    setSaving(true);
    setError("");

    const payload = {
      name: editing.name,
      category: editing.category,
      description: editing.description,
      rules: editing.rules,
      history: editing.history,
    };

    try {
      if (isNew) {
        const res = await api.post("/api/settings/world", payload);
        const newWorld = { ...editing, id: res.id };
        setWorlds((prev) => [...prev, newWorld]);
      } else {
        await api.put(`/api/settings/world/${editing.id}`, payload);
        setWorlds((prev) =>
          prev.map((w) => (w.id === editing.id ? editing : w))
        );
      }
      setShowForm(false);
      setEditing(null);
    } catch (e: any) {
      console.error("保存世界观失败:", e);
      setError(e?.message || "保存失败，请检查网络连接");
    }
    setSaving(false);
  };

  return (
    <div style={{ padding: "16px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>世界观设定 ({worlds.length})</h3>
        <button
          onClick={handleAdd}
          style={{
            padding: "8px 16px", background: "#8b5cf6", color: "#fff",
            border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13,
          }}
        >
          + 新建世界观
        </button>
      </div>

      {loading ? (
        <p style={{ color: "#9ca3af", fontSize: 13 }}>加载中...</p>
      ) : worlds.length === 0 ? (
        <p style={{ color: "#9ca3af", fontSize: 13 }}>暂无世界观设定，点击"新建世界观"创建</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {/* 批量操作栏 */}
          {selectedIds.size > 0 && (
            <div style={{ padding: "8px 12px", background: "#eff6ff", borderBottom: "1px solid #bfdbfe", display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
              <span style={{ color: "#1d4ed8", flex: 1 }}>已选 {selectedIds.size} 项</span>
              <button onClick={toggleSelectAll} style={{ padding: "4px 8px", border: "1px solid #93c5fd", borderRadius: 4, background: "#fff", cursor: "pointer", color: "#2563eb" }}>全选 ({worlds.length})</button>
              <button onClick={() => setSelectedIds(new Set())} style={{ padding: "4px 8px", border: "1px solid #d1d5db", borderRadius: 4, background: "#fff", cursor: "pointer", color: "#6b7280" }}>取消选择</button>
              <button onClick={batchDelete} style={{ padding: "4px 12px", border: "none", borderRadius: 4, background: "#ef4444", cursor: "pointer", color: "#fff", fontWeight: 600 }}>删除 {selectedIds.size} 项</button>
            </div>
          )}
          {worlds.map((world) => (
            <div key={world.id} style={{ display: "flex", alignItems: "flex-start" }}>
              <input
                type="checkbox"
                checked={selectedIds.has(world.id)}
                onChange={() => toggleSelect(world.id)}
                style={{ margin: "14px 10px 0 0", cursor: "pointer", width: 16, height: 16, flexShrink: 0 }}
                onClick={(e) => e.stopPropagation()}
              />
              <div
                style={{
                  border: "1px solid #e5e7eb", borderRadius: 8, padding: 12,
                  background: "#fafafa", display: "flex", justifyContent: "space-between",
                  alignItems: "flex-start", flex: 1,
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>{world.name}</div>
                  <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 2 }}>
                    {world.category || "未分类"} | {world.description?.slice(0, 60) || "未设定描述"}
                  </div>
                  {world.rules && world.rules.length > 0 && (
                    <div style={{ fontSize: 11, color: "#9ca3af" }}>
                      规则: {world.rules.slice(0, 3).join(" / ")}
                    </div>
                  )}
                  {world.history && world.history.length > 0 && (
                    <div style={{ fontSize: 11, color: "#9ca3af" }}>
                      历史: {world.history.slice(0, 2).join(" / ")}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                  <button
                    onClick={() => handleEdit(world)}
                    style={{
                      padding: "4px 12px", background: "#e5e7eb", border: "none",
                      borderRadius: 4, cursor: "pointer", fontSize: 12,
                    }}
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => handleDelete(world.id)}
                    style={{
                      padding: "4px 12px", background: "#fee2e2", color: "#991b1b",
                      border: "none", borderRadius: 4, cursor: "pointer", fontSize: 12,
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 编辑/新建弹窗 */}
      {showForm && editing && (
        <div
          style={{
            position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
            background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center",
            justifyContent: "center", zIndex: 1000,
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowForm(false); }}
        >
          <div
            style={{
              background: "#fff", borderRadius: 12, padding: 24,
              width: "90%", maxWidth: 600, maxHeight: "85vh", overflow: "auto",
              boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
            }}
          >
            <h3 style={{ margin: "0 0 16px", fontSize: 16 }}>
              {isNew ? "新建世界观" : `编辑世界观 — ${editing.name}`}
            </h3>

            {error && (
              <div style={{ padding: "8px 12px", background: "#fef2f2", color: "#991b1b", borderRadius: 6, marginBottom: 12, fontSize: 13 }}>
                {error}
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", gap: 8 }}>
                <div style={{ flex: 2 }}>
                  <Label>世界观名称 *</Label>
                  <Input value={editing.name} onChange={(v) => setEditing({ ...editing, name: v })} placeholder="如：玄天大陆" />
                </div>
                <div style={{ flex: 1 }}>
                  <Label>类型</Label>
                  <select
                    value={editing.category}
                    onChange={(e) => setEditing({ ...editing, category: e.target.value })}
                    style={inputStyle}
                  >
                    <option value="">— 选择 —</option>
                    {CATEGORY_OPTIONS.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* AI 模型选择 + 自动生成按钮 */}
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {llmConfigs.length > 0 && (
                <select
                  value={selectedConfigId}
                  onChange={(e) => setSelectedConfigId(e.target.value)}
                  style={{
                    padding: "8px 12px", borderRadius: 6, border: "1px solid #d1d5db",
                    fontSize: 13, outline: "none", background: "#fff", color: "#374151",
                    minWidth: 160,
                  }}
                >
                  {llmConfigs.map((c: any) => (
                    <option key={c.id} value={c.id}>
                      {c.is_default ? "⭐ " : ""}{c.name} ({c.model || c.provider})
                    </option>
                  ))}
                </select>
              )}
              <button
                onClick={handleAiGen}
                disabled={aiGenerating || !editing.name.trim() || llmConfigs.length === 0}
                style={{
                  padding: "8px 16px", alignSelf: "flex-start",
                  background: aiGenerating ? "#c7d2fe" : "#6366f1", color: "#fff",
                  border: "none", borderRadius: 6, cursor: (aiGenerating || llmConfigs.length === 0) ? "not-allowed" : "pointer",
                  fontSize: 13, opacity: (aiGenerating || llmConfigs.length === 0) ? 0.7 : 1,
                }}
              >
                {llmConfigs.length === 0 ? "请先配置LLM模型" : aiGenerating ? "AI生成中..." : "🤖 AI自动生成世界观详情"}
              </button>
            </div>

              <div>
                <Label>世界观描述 {editing.description && <span style={{ color: "#10b981", fontWeight: 400 }}>({editing.description.length}字)</span>}</Label>
                <Textarea value={editing.description} onChange={(v) => setEditing({ ...editing, description: v })} placeholder="描述这个世界的核心设定、地理、时代背景、势力分布..." rows={5} />
              </div>
              <div>
                <Label>世界规则（每行一条）{editing.rules.length > 0 && <span style={{ color: "#10b981", fontWeight: 400 }}>({editing.rules.length}条)</span>}</Label>
                <Textarea value={editing.rules.join("\n")} onChange={(v) => setEditing({ ...editing, rules: v.split("\n").filter(Boolean) })} placeholder="如：灵力分为九阶，修炼需经过天劫淬体&#10;如：只有被选中者才能穿越界域之门" rows={5} />
              </div>
              <div>
                <Label>世界历史（每行一条）{editing.history.length > 0 && <span style={{ color: "#10b981", fontWeight: 400 }}>({editing.history.length}条)</span>}</Label>
                <Textarea value={editing.history.join("\n")} onChange={(v) => setEditing({ ...editing, history: v.split("\n").filter(Boolean) })} placeholder="如：上古时期，神族与魔族大战，大陆崩裂为三块&#10;如：五百年前，第一位觉醒者出现" rows={5} />
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 20, justifyContent: "flex-end" }}>
              <button
                onClick={() => { setShowForm(false); setEditing(null); }}
                style={{ padding: "8px 20px", background: "#e5e7eb", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13 }}
              >
                取消
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                style={{
                  padding: "8px 20px", background: "#8b5cf6", color: "#fff",
                  border: "none", borderRadius: 6, cursor: saving ? "not-allowed" : "pointer",
                  fontSize: 13, opacity: saving ? 0.7 : 1,
                }}
              >
                {saving ? "保存中..." : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Label({ children, style }: { children: any; style?: React.CSSProperties }) {
  return <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 4, ...style }}>{children}</div>;
}

function Input({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={inputStyle} />
  );
}

function Textarea({ value, onChange, placeholder, rows = 3 }: { value: string; onChange: (v: string) => void; placeholder?: string; rows?: number }) {
  return (
    <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={rows} style={{ ...inputStyle, resize: "vertical" }} />
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "8px 12px", border: "1px solid #d1d5db",
  borderRadius: 6, fontSize: 13, boxSizing: "border-box",
  fontFamily: "inherit",
};