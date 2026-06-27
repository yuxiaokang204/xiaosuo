/**
 * CharactersPage — 角色管理页（重构自 CharacterManager.tsx）
 */
import React, { useState, useEffect, useCallback } from "react";

interface Character {
  id?: string; name: string; role?: string; personality?: string;
  background?: string; goals?: string[]; speech_pattern?: string;
  appearance?: string; aliases?: string[];
}

export const CharactersPage: React.FC = () => {
  const [presets, setPresets] = useState<Character[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editChar, setEditChar] = useState<Character | null>(null);
  const [formData, setFormData] = useState<Character>({ name: "", role: "配角", personality: "", background: "" });

  const loadPresets = useCallback(async () => {
    try {
      const data = await fetch("/api/presets").then((r) => r.json());
      setPresets(data.characters || []);
    } catch {}
  }, []);

  useEffect(() => { loadPresets(); }, [loadPresets]);

  const saveChar = async () => {
    try {
      if (editChar?.id) {
        await fetch(`/api/settings/character/${editChar.id}`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(formData),
        });
      } else {
        await fetch("/api/settings/character", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(formData),
        });
      }
      setShowForm(false);
      setEditChar(null);
      loadPresets();
    } catch (e: any) { alert(e.message); }
  };

  const deleteChar = async (id: string) => {
    if (!confirm("确定删除？")) return;
    try {
      await fetch(`/api/settings/character/${id}`, { method: "DELETE" });
      loadPresets();
    } catch (e: any) { alert(e.message); }
  };

  const openAI = async () => {
    try {
      const r = await fetch("/api/create/character-auto", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: "主角" }),
      });
      const data = await r.json();
      setPresets((prev) => [...prev, data]);
    } catch (e: any) { alert(e.message); }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>👥 角色管理</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button onClick={() => { setFormData({ name: "", role: "配角", personality: "", background: "" }); setShowForm(true); }} className="btn btn-primary">+ 新建角色</button>
        <button onClick={openAI} className="btn btn-secondary">🤖 AI 生成角色</button>
      </div>

      {presets.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", background: "var(--bg-primary)", borderRadius: 12 }}>暂无角色</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
          {presets.map((char, i) => (
            <div key={i} className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                <div>
                  <h4 style={{ margin: 0, fontSize: 16 }}>{char.name}</h4>
                  <span className="badge badge-info" style={{ marginTop: 4 }}>{char.role || "配角"}</span>
                </div>
                <div style={{ display: "flex", gap: 4 }}>
                  <button onClick={() => { setEditChar(char); setFormData(char); setShowForm(true); }} className="btn btn-ghost btn-sm">编辑</button>
                  <button onClick={() => deleteChar(char.id!)} className="btn btn-ghost btn-sm" style={{ color: "var(--danger)" }}>删除</button>
                </div>
              </div>
              {char.personality && <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 8 }}>{char.personality}</p>}
              {char.background && <p style={{ fontSize: 12, color: "var(--text-muted)" }}>{char.background.slice(0, 100)}...</p>}
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: 440 }}>
            <div className="modal-header"><h3 style={{ fontSize: 16, margin: 0 }}>{editChar ? "编辑角色" : "新建角色"}</h3>
              <button onClick={() => setShowForm(false)} className="btn btn-ghost">✕</button></div>
            <div className="modal-body">
              {[
                { label: "名字", field: "name" as const },
                { label: "角色", field: "role" as const },
              ].map(({ label, field }) => (
                <div key={field} style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>{label}</label>
                  <input type="text" value={formData[field] as string} onChange={(e) => setFormData({ ...formData, [field]: e.target.value })} className="input" />
                </div>
              ))}
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>性格</label>
                <textarea value={formData.personality} onChange={(e) => setFormData({ ...formData, personality: e.target.value })} className="textarea" rows={2} />
              </div>
              <div>
                <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>背景</label>
                <textarea value={formData.background} onChange={(e) => setFormData({ ...formData, background: e.target.value })} className="textarea" rows={2} />
              </div>
            </div>
            <div className="modal-footer">
              <button onClick={() => setShowForm(false)} className="btn btn-secondary">取消</button>
              <button onClick={saveChar} className="btn btn-primary">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
