import { useState, useEffect, useCallback } from "react";
import { api } from "../api";

interface Character {
  id: string;
  name: string;
  role: string;
  personality: string;
  background: string;
  appearance: string;
  goals: string[];
  conflicts: string[];
  speech_pattern: string;
  aliases: string[];
  arc_data: any;
  world_id?: string;
  novel_id?: string;
}

interface WorldSetting {
  id: string;
  name: string;
  category: string;
  description: string;
  rules: string[];
  history: string[];
}

const emptyCharacter: Character = {
  id: "", name: "", role: "", personality: "", background: "",
  appearance: "", goals: [], conflicts: [], speech_pattern: "",
  aliases: [], arc_data: {}, world_id: "",
};

const ROLE_OPTIONS = ["主角", "配角", "反派", "导师", "盟友", "路人", "其他"];

export default function CharacterManager() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [worlds, setWorlds] = useState<WorldSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Character | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [error, setError] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // LLM 配置选择
  const [llmConfigs, setLlmConfigs] = useState<any[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getPresets();
      const chars = (data.characters || []).map((c: any) => ({
        id: c.id || "",
        name: c.name || "",
        role: c.role || "",
        personality: c.personality || "",
        background: c.background || "",
        appearance: c.appearance || "",
        goals: c.goals || [],
        conflicts: c.conflicts || [],
        speech_pattern: c.speech_pattern || "",
        aliases: c.aliases || [],
        arc_data: c.arc_data || {},
        world_id: c.world_id || "",
        novel_id: c.novel_id,
      }));
      setCharacters(chars);

      const wItems = (data.world_settings || []).map((w: any) => ({
        id: w.id || "",
        name: w.name || "",
        category: w.category || "",
        description: w.description || "",
        rules: w.rules || [],
        history: w.history || [],
      }));
      setWorlds(wItems);
    } catch (e) {
      console.error("加载数据失败:", e);
    }
    setLoading(false);

    // 加载LLM配置
    try {
      const llmData = await api.get("/api/llm/configs");
      setLlmConfigs(llmData.configs || []);
      const def = (llmData.configs || []).find((c: any) => c.is_default);
      setSelectedConfigId(def?.id || ((llmData.configs || [])[0]?.id || ""));
    } catch { /* 忽略加载失败 */ }
  }, []);

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAdd = () => {
    setEditing({ ...emptyCharacter });
    setIsNew(true);
    setShowForm(true);
    setError("");
  };

  const handleEdit = (char: Character) => {
    setEditing({ ...char });
    setIsNew(false);
    setShowForm(true);
    setError("");
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("确定删除此角色？此操作不可撤销。")) return;
    try {
      await api.delete(`/api/settings/character/${id}`);
      setCharacters((prev) => prev.filter((c) => c.id !== id));
    } catch (e) {
      console.error("删除角色失败:", e);
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
    if (selectedIds.size === characters.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(characters.map((c) => c.id)));
    }
  };

  // 批量删除
  const batchDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`确定删除选中的 ${selectedIds.size} 个角色？此操作不可恢复。`)) return;
    try {
      await fetch("/api/settings/character/batch-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([...selectedIds]),
      });
      setCharacters((prev) => prev.filter((c) => !selectedIds.has(c.id)));
      setSelectedIds(new Set());
    } catch (e: any) {
      console.error("批量删除角色失败:", e);
      setError("批量删除失败，请重试");
    }
  };

  // ── AI 自动生成角色属性 ──
  const handleAiGen = async () => {
    if (!editing) return;
    const name = editing.name.trim();
    if (!name) {
      setError("请先输入角色名称");
      return;
    }
    setAiGenerating(true);
    setError("");

    // 获取已选择的世界观信息
    let worldInfo = { world_name: "", world_category: "", world_description: "", world_rules: [] as string[] };
    if (editing.world_id) {
      const boundWorld = worlds.find((w) => w.id === editing.world_id);
      if (boundWorld) {
        worldInfo = {
          world_name: boundWorld.name,
          world_category: boundWorld.category,
          world_description: boundWorld.description,
          world_rules: boundWorld.rules,
        };
      }
    }

    try {
      const res = await api.post("/api/create/character-auto", {
        name: editing.name,
        role: editing.role || "主角",
        config_id: selectedConfigId,
        ...worldInfo,
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
        personality: data.personality || editing.personality,
        background: data.background || editing.background,
        appearance: data.appearance || editing.appearance,
        goals: data.goals || editing.goals,
        conflicts: data.conflicts || editing.conflicts,
        speech_pattern: data.speech_pattern || editing.speech_pattern,
        aliases: data.aliases || editing.aliases,
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
      setError("角色名称不能为空");
      return;
    }

    setSaving(true);
    setError("");

    const payload = {
      name: editing.name,
      role: editing.role,
      personality: editing.personality,
      background: editing.background,
      appearance: editing.appearance,
      goals: editing.goals,
      conflicts: editing.conflicts,
      speech_pattern: editing.speech_pattern,
      aliases: editing.aliases,
      arc_data: editing.arc_data,
      world_id: editing.world_id,
    };

    try {
      if (isNew) {
        const res = await api.post("/api/settings/character", payload);
        const newChar = { ...editing, id: res.id };
        setCharacters((prev) => [...prev, newChar]);
      } else {
        await api.put(`/api/settings/character/${editing.id}`, payload);
        setCharacters((prev) =>
          prev.map((c) => (c.id === editing.id ? editing : c))
        );
      }
      setShowForm(false);
      setEditing(null);
    } catch (e: any) {
      console.error("保存角色失败:", e);
      setError(e?.message || "保存失败，请检查网络连接");
    }
    setSaving(false);
  };

  // 获取世界观名称
  const getWorldName = (worldId?: string) => {
    if (!worldId) return "";
    const w = worlds.find((w) => w.id === worldId);
    return w ? w.name : "";
  };

  return (
    <div style={{ padding: "16px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>角色管理 ({characters.length})</h3>
        <button
          onClick={handleAdd}
          style={{
            padding: "8px 16px", background: "#3b82f6", color: "#fff",
            border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13,
          }}
        >
          + 新建角色
        </button>
      </div>

      {loading ? (
        <p style={{ color: "#9ca3af", fontSize: 13 }}>加载中...</p>
      ) : characters.length === 0 ? (
        <p style={{ color: "#9ca3af", fontSize: 13 }}>暂无角色，点击"新建角色"创建</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {/* 批量操作栏 */}
          {selectedIds.size > 0 && (
            <div style={{ padding: "8px 12px", background: "#eff6ff", borderBottom: "1px solid #bfdbfe", display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
              <span style={{ color: "#1d4ed8", flex: 1 }}>已选 {selectedIds.size} 项</span>
              <button onClick={toggleSelectAll} style={{ padding: "4px 8px", border: "1px solid #93c5fd", borderRadius: 4, background: "#fff", cursor: "pointer", color: "#2563eb" }}>全选 ({characters.length})</button>
              <button onClick={() => setSelectedIds(new Set())} style={{ padding: "4px 8px", border: "1px solid #d1d5db", borderRadius: 4, background: "#fff", cursor: "pointer", color: "#6b7280" }}>取消选择</button>
              <button onClick={batchDelete} style={{ padding: "4px 12px", border: "none", borderRadius: 4, background: "#ef4444", cursor: "pointer", color: "#fff", fontWeight: 600 }}>删除 {selectedIds.size} 项</button>
            </div>
          )}
          {characters.map((char) => (
            <div key={char.id} style={{ display: "flex", alignItems: "flex-start" }}>
              <input
                type="checkbox"
                checked={selectedIds.has(char.id)}
                onChange={() => toggleSelect(char.id)}
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
                  <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>
                    {char.name}
                    {getWorldName(char.world_id) && (
                      <span style={{ fontSize: 11, color: "#8b5cf6", marginLeft: 8, fontWeight: 400 }}>
                        @{getWorldName(char.world_id)}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 2 }}>
                    {char.role || "未设定"} | {char.personality?.slice(0, 40) || "未设定性格"}
                  </div>
                  {char.goals && char.goals.length > 0 && (
                    <div style={{ fontSize: 11, color: "#9ca3af" }}>
                      目标: {char.goals.slice(0, 2).join(" / ")}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                  <button
                    onClick={() => handleEdit(char)}
                    style={{
                      padding: "4px 12px", background: "#e5e7eb", border: "none",
                      borderRadius: 4, cursor: "pointer", fontSize: 12,
                    }}
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => handleDelete(char.id)}
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
              {isNew ? "新建角色" : `编辑角色 — ${editing.name}`}
            </h3>

            {error && (
              <div style={{ padding: "8px 12px", background: "#fef2f2", color: "#991b1b", borderRadius: 6, marginBottom: 12, fontSize: 13 }}>
                {error}
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", gap: 8 }}>
                <div style={{ flex: 2 }}>
                  <Label>角色名称 *</Label>
                  <Input value={editing.name} onChange={(v) => setEditing({ ...editing, name: v })} placeholder="如：林深" />
                </div>
                <div style={{ flex: 1 }}>
                  <Label>角色定位</Label>
                  <select
                    value={editing.role}
                    onChange={(e) => setEditing({ ...editing, role: e.target.value })}
                    style={inputStyle}
                  >
                    <option value="">— 选择 —</option>
                    {ROLE_OPTIONS.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* 世界观绑定 */}
              <div>
                <Label>绑定世界观</Label>
                <select
                  value={editing.world_id || ""}
                  onChange={(e) => setEditing({ ...editing, world_id: e.target.value })}
                  style={inputStyle}
                >
                  <option value="">— 不绑定 —</option>
                  {worlds.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name} ({w.category})
                    </option>
                  ))}
                </select>
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
                    background: aiGenerating ? "#bfdbfe" : "#3b82f6", color: "#fff",
                    border: "none", borderRadius: 6, cursor: (aiGenerating || llmConfigs.length === 0) ? "not-allowed" : "pointer",
                    fontSize: 13, opacity: (aiGenerating || llmConfigs.length === 0) ? 0.7 : 1,
                  }}
                >
                  {llmConfigs.length === 0 ? "请先配置LLM模型" : aiGenerating ? "AI生成中..." : `🤖 AI自动生成角色属性${editing.world_id ? "（基于世界观）" : ""}`}
                </button>
              </div>

              <div>
                <Label>性格特征 {editing.personality && <span style={{ color: "#10b981", fontWeight: 400 }}>({editing.personality.length}字)</span>}</Label>
                <Textarea value={editing.personality} onChange={(v) => setEditing({ ...editing, personality: v })} placeholder="如：冷静、谨慎、有正义感，但对信任的人会展现温柔一面" />
              </div>
              <div>
                <Label>背景故事</Label>
                <Textarea value={editing.background} onChange={(v) => setEditing({ ...editing, background: v })} placeholder="角色的出身、经历、关键事件..." rows={4} />
              </div>
              <div>
                <Label>外貌描述</Label>
                <Textarea value={editing.appearance} onChange={(v) => setEditing({ ...editing, appearance: v })} placeholder="如：左手食指有旧伤疤，习惯穿深色衣服..." />
              </div>
              <div>
                <Label>目标（每行一个）{editing.goals.length > 0 && <span style={{ color: "#10b981", fontWeight: 400 }}>({editing.goals.length}个)</span>}</Label>
                <Textarea value={editing.goals.join("\n")} onChange={(v) => setEditing({ ...editing, goals: v.split("\n").filter(Boolean) })} placeholder="如：找到失踪的同伴&#10;如：揭开自己的身世之谜" />
              </div>
              <div>
                <Label>冲突（每行一个）{editing.conflicts.length > 0 && <span style={{ color: "#10b981", fontWeight: 400 }}>({editing.conflicts.length}个)</span>}</Label>
                <Textarea value={editing.conflicts.join("\n")} onChange={(v) => setEditing({ ...editing, conflicts: v.split("\n").filter(Boolean) })} placeholder="如：与上级理念不合&#10;如：对自身能力的不自信" />
              </div>
              <div>
                <Label>说话方式</Label>
                <Input value={editing.speech_pattern} onChange={(v) => setEditing({ ...editing, speech_pattern: v })} placeholder="如：简洁有力，偶尔带冷笑" />
              </div>
              <div>
                <Label>别名（逗号分隔）</Label>
                <Input value={editing.aliases.join(", ")} onChange={(v) => setEditing({ ...editing, aliases: v.split(",").map((s) => s.trim()).filter(Boolean) })} placeholder="如：阿深, 林队" />
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
                  padding: "8px 20px", background: "#3b82f6", color: "#fff",
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

function Label({ children }: { children: any }) {
  return <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 4 }}>{children}</div>;
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