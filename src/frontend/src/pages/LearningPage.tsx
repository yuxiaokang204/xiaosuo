/**
 * LearningPage — 学习引擎管理页
 */
import React, { useState, useEffect, useCallback } from "react";

export const LearningPage: React.FC = () => {
  const [stats, setStats] = useState<any>(null);
  const [feedbackType, setFeedbackType] = useState("style_edit");
  const [beforeText, setBeforeText] = useState("");
  const [afterText, setAfterText] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [clearing, setClearing] = useState(false);

  const loadStats = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetch("/api/learning/stats").then((r) => r.json()).catch(() => null);
      setStats(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  const submitFeedback = async () => {
    if (!beforeText.trim() || !afterText.trim()) return;
    setSubmitting(true);
    try {
      await fetch("/api/learning/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback_type: feedbackType, before_text: beforeText, after_text: afterText }),
      });
      setBeforeText("");
      setAfterText("");
      loadStats();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const clearLearning = async () => {
    if (!confirm("确定清空所有学习数据？这将清除已学到的风格偏好和反AI模式。")) return;
    setClearing(true);
    try {
      await fetch("/api/learning/clear", { method: "POST" });
      setStats(null);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setClearing(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>🧠 学习引擎</h2>

      {/* 使用说明 */}
      <div style={{
        background: "var(--bg-primary)",
        border: "1px solid var(--border)",
        borderLeft: "3px solid var(--accent)",
        borderRadius: 12,
        padding: 20,
        marginBottom: 24,
      }}>
        <h3 style={{ fontSize: 14, margin: "0 0 12px", color: "var(--accent)" }}>💡 使用说明</h3>
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.8 }}>
          <li><b>作用</b>：学习引擎会从你的编辑行为中提取写作偏好，自动应用到后续章节生成</li>
          <li><b>反馈类型</b>：
            <span style={{ color: "var(--text-muted)" }}>风格编辑</span>（用词/句式偏好）、
            <span style={{ color: "var(--text-muted)" }}>角色编辑</span>（人设调整）、
            <span style={{ color: "var(--text-muted)" }}>情节编辑</span>（剧情走向）、
            <span style={{ color: "var(--text-muted)" }}>删除</span>（不喜欢的表达）、
            <span style={{ color: "var(--text-muted)" }}>喜欢</span>（强化某种风格）
          </li>
          <li><b>提交方式</b>：在下方表单填入「修改前」和「修改后」文本，提交后引擎会自动 diff 出差异并学习</li>
          <li><b>应用时机</b>：学习到的模式会在下一次「全流程创作」或「单章生成」时自动注入到 prompt 中</li>
          <li><b>清空数据</b>：点击「清空学习数据」可重置所有学到的偏好（不影响已生成的章节）</li>
        </ul>
      </div>

      {/* 统计 */}
      <div style={{
        background: "var(--bg-primary)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: 24,
        marginBottom: 24,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, margin: 0 }}>统计数据</h3>
          <button onClick={clearLearning} disabled={clearing} className="btn btn-danger btn-sm">
            {clearing ? "清空中..." : "🗑 清空学习数据"}
          </button>
        </div>
        {loading ? (
          <div className="skeleton" style={{ height: 120, borderRadius: 8 }} />
        ) : stats ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
            {[
              { label: "总反馈数", value: stats.total_feedback ?? 0 },
              { label: "风格编辑", value: stats.style_edits ?? 0 },
              { label: "角色编辑", value: stats.character_edits ?? 0 },
              { label: "学到模式", value: stats.learned_patterns ?? 0 },
              { label: "反AI模式", value: stats.anti_ai_patterns ?? 0 },
            ].map((item, i) => (
              <div key={i} style={{ padding: 12, background: "var(--bg-secondary)", borderRadius: 8 }}>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{item.label}</span>
                <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4 }}>{item.value}</div>
              </div>
            ))}
          </div>
        ) : (
          <span style={{ color: "var(--text-muted)" }}>暂无数据</span>
        )}
      </div>

      {/* 提交反馈 */}
      <div style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: 12, padding: 24 }}>
        <h3 style={{ fontSize: 16, marginBottom: 16 }}>提交反馈</h3>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>反馈类型</label>
          <select value={feedbackType} onChange={(e) => setFeedbackType(e.target.value)} className="select">
            <option value="style_edit">风格编辑</option>
            <option value="character_edit">角色编辑</option>
            <option value="plot_edit">情节编辑</option>
            <option value="deletion">删除</option>
            <option value="like">喜欢</option>
          </select>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>修改前文本</label>
          <textarea value={beforeText} onChange={(e) => setBeforeText(e.target.value)} className="textarea" rows={3} placeholder="AI 生成的原始文本" />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 13, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>修改后文本</label>
          <textarea value={afterText} onChange={(e) => setAfterText(e.target.value)} className="textarea" rows={3} placeholder="你修改后的版本" />
        </div>
        <button onClick={submitFeedback} disabled={submitting || !beforeText.trim() || !afterText.trim()} className="btn btn-primary">
          {submitting ? "提交中..." : "📤 提交反馈"}
        </button>
      </div>
    </div>
  );
};
