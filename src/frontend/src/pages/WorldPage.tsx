/**
 * WorldPage — 世界观设定管理页（重构自 WorldSettingManager.tsx）
 */
import React, { useState, useEffect, useCallback } from "react";

interface WorldSetting {
  id?: string; name: string; description?: string; rules?: string[];
}

export const WorldPage: React.FC = () => {
  const [presets, setPresets] = useState<WorldSetting[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editSetting, setEditSetting] = useState<WorldSetting | null>(null);
  const [formData, setFormData] = useState<WorldSetting>({ name: "", description: "" });

  const loadPresets = useCallback(async () => {
    try {
      const data = await fetch("/api/presets").then((r) => r.json());
      setPresets(data.world_settings || []);
    } catch {}
  }, []);

  useEffect(() => { loadPresets(); }, [loadPresets]);

  const save = async () => {
    try {
      if (editSetting?.id) {
        await fetch(`/api/settings/world/${editSetting.id}`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(formData),
        });
      } else {
        await fetch("/api/settings/world", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(formData),
        });
      }
      setShowForm(false);
      setEditSetting(null);
      loadPresets();
    } catch (e: any) { alert(e.message); }
  };

  const del = async (id: string) => {
    if (!confirm("确定删除？")) return;
    try { await fetch(`/api/settings/world/${id}`, { method: "DELETE" }); loadPresets(); }
    catch (e: any) { alert(e.message); }
  };

  const openAI = async () => {
    try {
      const r = await fetch("/api/create/world-auto", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await r.json();
      setPresets((prev) => [...prev, data]);
    } catch (e: any) { alert(e.message); }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>🌍 世界观设定</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button onClick={() => { setFormData({ name: "", description: "" }); setShowForm(true); }} className="btn btn-primary">+ 新建设定</button>
        <button onClick={openAI} className="btn btn-secondary">🤖 AI 生成世界观</button>
      </div>

      {presets.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", background: "var(--bg-primary)", borderRadius: 12 }}>暂无设定</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
          {presets.map((ws, i) => (
            <div key={i} className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                <h4 style={{ margin: 0, fontSize: 16 }}>{ws.name}</h4>
                <div style={{ display: "flex", gap: 4 }}>
                  <button onClick={() => { setEditSetting(ws); setFormData(ws); setShowForm(true); }} className="btn btn-ghost btn-sm">编辑</button>
                  <button onClick={() => del(ws.id!)} className="btn btn-ghost btn-sm" style={{ color: "var(--danger)" }}>删除</button>
                </div>
              </div>
              {ws.description && <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 8 }}>{ws.description}</p>}
              {ws.rules && ws.rules.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  {ws.rules.map((r, ri) => (
                    <div key={ri} style={{ fontSize: 12, color: "var(--text-muted)", padding: "2px 0" }}>📜 {r}</div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: 440 }}>
            <div className="modal-header"><h3 style={{ fontSize: 16, margin: 0 }}>{editSetting ? "编辑设定" : "新建设定"}</h3>
              <button onClick={() => setShowForm(false)} className="btn btn-ghost">✕</button></div>
            <div className="modal-body">
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>名称</label>
                <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="input" />
              </div>
              <div>
                <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>描述</label>
                <textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} className="textarea" rows={3} />
              </div>
            </div>
            <div className="modal-footer">
              <button onClick={() => setShowForm(false)} className="btn btn-secondary">取消</button>
              <button onClick={save} className="btn btn-primary">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
