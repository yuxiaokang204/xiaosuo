/**
 * PromptManagerPage — 6 个 Skill Agent 提示词可视化管理
 *
 * 功能：
 *  - 按 agent_type / prompt_type 筛选
 *  - 查看/编辑/删除/激活 Prompt
 *  - 恢复默认（删除 DB 记录，回退到 prompts.py 硬编码）
 *  - 缓存清除（热更新）
 */

import React, { useState, useEffect, useCallback, useRef } from "react";

const AGENT_TYPES = [
  { value: "story_architect", label: "故事架构师" },
  { value: "world", label: "世界观构建师" },
  { value: "character", label: "角色塑造师" },
  { value: "opening_hook", label: "开篇钩子师" },
  { value: "draft", label: "专业写手" },
  { value: "style_editor", label: "文风精修师" },
];

const PROMPT_TYPES = [
  { value: "system", label: "System Prompt" },
  { value: "user", label: "User Prompt 模板" },
];

interface PromptItem {
  id: string;
  novel_id: string | null;
  agent_type: string;
  prompt_type: string;
  title: string;
  content: string;
  quality_score: number;
  usage_count: number;
  is_active: boolean;
  metadata: any;
  created_at: string;
  updated_at: string;
}

export const PromptManagerPage: React.FC = () => {
  const [prompts, setPrompts] = useState<PromptItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 筛选条件
  const [filterAgentType, setFilterAgentType] = useState("");
  const [filterPromptType, setFilterPromptType] = useState("");
  const [activeOnly, setActiveOnly] = useState(false);

  // 编辑状态
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [editScore, setEditScore] = useState(80);

  // 新建状态
  const [showCreate, setShowCreate] = useState(false);
  const [newAgentType, setNewAgentType] = useState("story_architect");
  const [newPromptType, setNewPromptType] = useState("system");
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");

  // 消息
  const [msg, setMsg] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const seededRef = useRef(false);

  const showMsg = (text: string, duration = 3000) => {
    setMsg(text);
    if (duration > 0) setTimeout(() => setMsg(""), duration);
  };

  const loadPrompts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filterAgentType) params.set("agent_type", filterAgentType);
      if (filterPromptType) params.set("prompt_type", filterPromptType);
      if (activeOnly) params.set("active_only", "true");
      const r = await fetch(`/api/prompts?${params.toString()}`);
      const data = await r.json();
      const list = data.prompts || [];
      if (list.length === 0 && !filterAgentType && !filterPromptType && !activeOnly && !seededRef.current) {
        seededRef.current = true;
        await fetch("/api/prompts/seed-defaults", { method: "POST" });
        const r2 = await fetch(`/api/prompts?${params.toString()}`);
        const data2 = await r2.json();
        setPrompts(data2.prompts || []);
        showMsg("已自动初始化 6 个 Agent 的 Skill 默认模板");
      } else {
        setPrompts(list);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filterAgentType, filterPromptType, activeOnly]);

  useEffect(() => {
    loadPrompts();
  }, [loadPrompts]);

  // 激活
  const activatePrompt = async (id: string) => {
    try {
      await fetch(`/api/prompts/${id}/activate`, { method: "POST" });
      showMsg("已激活，下次生成将使用此 Prompt");
      await fetch("/api/prompts/cache-clear", { method: "POST" });
      loadPrompts();
    } catch (e: any) {
      showMsg(`激活失败: ${e.message}`);
    }
  };

  // 开始编辑
  const startEdit = (p: PromptItem) => {
    setEditingId(p.id);
    setEditContent(p.content);
    setEditTitle(p.title);
    setEditScore(p.quality_score);
  };

  // 保存编辑
  const saveEdit = async () => {
    if (!editingId) return;
    try {
      await fetch(`/api/prompts/${editingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: editTitle,
          content: editContent,
          quality_score: editScore,
        }),
      });
      showMsg("保存成功");
      setEditingId(null);
      await fetch("/api/prompts/cache-clear", { method: "POST" });
      loadPrompts();
    } catch (e: any) {
      showMsg(`保存失败: ${e.message}`);
    }
  };

  // 删除
  const deletePrompt = async (id: string) => {
    if (!confirm("确定删除此 Prompt？")) return;
    try {
      await fetch(`/api/prompts/${id}`, { method: "DELETE" });
      showMsg("已删除");
      loadPrompts();
    } catch (e: any) {
      showMsg(`删除失败: ${e.message}`);
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
    if (selectedIds.size === prompts.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(prompts.map((p) => p.id)));
    }
  };

  // 批量删除
  const batchDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`确定删除选中的 ${selectedIds.size} 个 Prompt？此操作不可恢复。`)) return;
    try {
      await fetch("/api/prompts/batch-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([...selectedIds]),
      });
      setPrompts((prev) => prev.filter((p) => !selectedIds.has(p.id)));
      setSelectedIds(new Set());
      showMsg(`已删除 ${selectedIds.size} 个 Prompt`);
    } catch (e: any) {
      showMsg(`批量删除失败: ${e.message}`);
    }
  };

  // 新建
  const createPrompt = async () => {
    if (!newContent.trim()) {
      showMsg("内容不能为空");
      return;
    }
    try {
      await fetch("/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_type: newAgentType,
          prompt_type: newPromptType,
          title: newTitle || `${newAgentType}`,
          content: newContent,
          quality_score: 80,
        }),
      });
      showMsg("创建成功");
      setShowCreate(false);
      setNewContent("");
      loadPrompts();
    } catch (e: any) {
      showMsg(`创建失败: ${e.message}`);
    }
  };

  // 缓存清除
  const clearCache = async () => {
    await fetch("/api/prompts/cache-clear", { method: "POST" });
    showMsg("缓存已清除，下次调用将加载最新 Prompt");
  };

  const agentLabel = (v: string) => AGENT_TYPES.find((a) => a.value === v)?.label || v;

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Agent Prompt 管理</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={clearCache} style={btnStyle}
            title="清除后端运行时缓存，使修改立即生效（热更新）">
            🔄 清除缓存
          </button>
          <button onClick={() => setShowCreate(true)} style={{ ...btnStyle, background: "var(--accent)", color: "#fff" }}>
            + 新建 Prompt
          </button>
        </div>
      </div>

      {msg && (
        <div style={{ padding: "8px 16px", marginBottom: 16, background: "var(--accent-light)", borderRadius: 8, fontSize: 14 }}>
          {msg}
        </div>
      )}

      {/* 筛选栏 */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <select value={filterAgentType} onChange={(e) => setFilterAgentType(e.target.value)}
          style={selectStyle}>
          <option value="">所有 Agent</option>
          {AGENT_TYPES.map((a) => (
            <option key={a.value} value={a.value}>{a.label}</option>
          ))}
        </select>
        <select value={filterPromptType} onChange={(e) => setFilterPromptType(e.target.value)}
          style={selectStyle}>
          <option value="">所有类型</option>
          {PROMPT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
          <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} />
          仅显示激活
        </label>
      </div>

      {error && <div style={{ color: "var(--danger)", marginBottom: 12 }}>{error}</div>}
      {loading && <div style={{ color: "var(--text-muted)" }}>加载中...</div>}

      {/* 提示词列表 */}
      {!loading && prompts.length === 0 && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
          暂无 Prompt 记录。点击"新建 Prompt"创建，或运行一次全流程编排自动生成。
        </div>
      )}

      {/* 批量操作栏 */}
      {selectedIds.size > 0 && (
        <div style={{ padding: "8px 12px", background: "var(--accent-light)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginBottom: 12 }}>
          <span style={{ color: "var(--accent)", flex: 1 }}>已选 {selectedIds.size} 项</span>
          <button onClick={toggleSelectAll} style={{ padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4, background: "var(--bg-primary)", cursor: "pointer", color: "var(--accent)" }}>全选 ({prompts.length})</button>
          <button onClick={() => setSelectedIds(new Set())} style={{ padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4, background: "var(--bg-primary)", cursor: "pointer", color: "var(--text-secondary)" }}>取消选择</button>
          <button onClick={batchDelete} style={{ padding: "4px 12px", border: "none", borderRadius: 4, background: "var(--danger)", cursor: "pointer", color: "var(--text-inverse)", fontWeight: 600 }}>删除 {selectedIds.size} 项</button>
        </div>
      )}

      {prompts.map((p) => (
        <div key={p.id} style={{ display: "flex", alignItems: "flex-start", marginBottom: 12 }}>
          <input
            type="checkbox"
            checked={selectedIds.has(p.id)}
            onChange={() => toggleSelect(p.id)}
            style={{ margin: "18px 10px 0 0", cursor: "pointer", width: 16, height: 16, flexShrink: 0 }}
            onClick={(e) => e.stopPropagation()}
          />
          <div style={{
            flex: 1,
            border: "1px solid var(--border)", borderRadius: 10, padding: 16,
            background: p.is_active ? "var(--accent-light)" : "var(--bg-primary)",
          borderLeft: p.is_active ? "4px solid var(--accent)" : "4px solid var(--border)",
        }}>
          {editingId === p.id ? (
            /* 编辑模式 */
            <div>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                  style={{ ...inputStyle, flex: 1 }} placeholder="标题" />
                <input type="number" value={editScore} onChange={(e) => setEditScore(Number(e.target.value))}
                  style={{ ...inputStyle, width: 80 }} min={0} max={100} title="质量评分 0-100" />
              </div>
              <textarea value={editContent} onChange={(e) => setEditContent(e.target.value)}
                style={{ ...inputStyle, width: "100%", minHeight: 200, fontFamily: "monospace", fontSize: 13 }}
                placeholder="Prompt 正文..." />
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <button onClick={saveEdit} style={{ ...btnStyle, background: "var(--accent)", color: "#fff" }}>保存</button>
                <button onClick={() => setEditingId(null)} style={btnStyle}>取消</button>
              </div>
            </div>
          ) : (
            /* 查看模式 */
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{p.title}</span>
                  <span style={{
                    fontSize: 11, padding: "2px 8px", borderRadius: 4,
                    background: "var(--bg-secondary)", color: "var(--text-secondary)",
                  }}>
                    {agentLabel(p.agent_type)} · {p.prompt_type}
                  </span>
                  {p.is_active && (
                    <span style={{
                      fontSize: 11, padding: "2px 8px", borderRadius: 4,
                      background: "var(--accent)", color: "#fff", fontWeight: 600,
                    }}>
                      激活中
                    </span>
                  )}
                  {p.novel_id && (
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>小说专属</span>
                  )}
                </div>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  评分: {p.quality_score} | 使用: {p.usage_count}次
                </span>
              </div>
              <pre style={{
                fontSize: 12, lineHeight: 1.5, color: "var(--text-secondary)",
                whiteSpace: "pre-wrap", maxHeight: 120, overflow: "hidden",
                margin: "8px 0", padding: 8, background: "var(--bg-secondary)", borderRadius: 6,
              }}>
                {p.content.slice(0, 300)}{p.content.length > 300 ? "..." : ""}
              </pre>
              <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                <button onClick={() => startEdit(p)} style={btnStyle}>✏️ 编辑</button>
                {!p.is_active && (
                  <button onClick={() => activatePrompt(p.id)} style={btnStyle}>✅ 激活</button>
                )}
                <button onClick={() => deletePrompt(p.id)} style={{ ...btnStyle, color: "var(--danger)" }}>🗑 删除</button>
              </div>
            </div>
          )}
        </div>
        </div>
      ))}

      {/* 新建弹窗 */}
      {showCreate && (
        <div style={overlayStyle}>
          <div style={modalStyle}>
            <h3 style={{ margin: "0 0 16px" }}>新建 Prompt</h3>
            <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
              <select value={newAgentType} onChange={(e) => setNewAgentType(e.target.value)} style={selectStyle}>
                {AGENT_TYPES.map((a) => (
                  <option key={a.value} value={a.value}>{a.label}</option>
                ))}
              </select>
              <select value={newPromptType} onChange={(e) => setNewPromptType(e.target.value)} style={selectStyle}>
                {PROMPT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)}
              style={{ ...inputStyle, width: "100%", marginBottom: 8 }}
              placeholder="标题（可选）" />
            <textarea value={newContent} onChange={(e) => setNewContent(e.target.value)}
              style={{ ...inputStyle, width: "100%", minHeight: 200, fontFamily: "monospace", fontSize: 13 }}
              placeholder="Prompt 正文..." />
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button onClick={createPrompt} style={{ ...btnStyle, background: "var(--accent)", color: "#fff" }}>创建</button>
              <button onClick={() => setShowCreate(false)} style={btnStyle}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const btnStyle: React.CSSProperties = {
  padding: "6px 14px",
  border: "1px solid var(--border)",
  borderRadius: 6,
  background: "var(--bg-secondary)",
  color: "var(--text-primary)",
  cursor: "pointer",
  fontSize: 13,
  fontWeight: 500,
};

const inputStyle: React.CSSProperties = {
  padding: "8px 12px",
  border: "1px solid var(--border)",
  borderRadius: 6,
  background: "var(--bg-primary)",
  color: "var(--text-primary)",
  fontSize: 13,
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  minWidth: 160,
};

const overlayStyle: React.CSSProperties = {
  position: "fixed", inset: 0,
  background: "rgba(0,0,0,0.4)",
  display: "flex", alignItems: "center", justifyContent: "center",
  zIndex: 1000,
};

const modalStyle: React.CSSProperties = {
  background: "var(--bg-primary)",
  borderRadius: 12,
  padding: 24,
  width: "90%",
  maxWidth: 700,
  maxHeight: "80vh",
  overflow: "auto",
  boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
};