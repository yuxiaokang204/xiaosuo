/**
 * DashboardPage — 仪表盘（重构自 DashboardPanel.tsx）
 */
import React, { useState, useEffect, useCallback } from "react";

export const DashboardPage: React.FC = () => {
  const [dashboard, setDashboard] = useState<any>(null);
  const [memoryStats, setMemoryStats] = useState<any>(null);
  const [learningStats, setLearningStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [d, m, l] = await Promise.all([
        fetch("/api/orchestrator/dashboard").then((r) => r.json()).catch(() => null),
        fetch("/api/memory/stats").then((r) => r.json()).catch(() => null),
        fetch("/api/learning/stats").then((r) => r.json()).catch(() => null),
      ]);
      setDashboard(d);
      setMemoryStats(m);
      setLearningStats(l);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadDashboard(); }, [loadDashboard]);

  const runConsistency = async () => {
    try {
      const r = await fetch("/api/orchestrator/check-consistency", { method: "POST" });
      const data = await r.json();
      alert(JSON.stringify(data, null, 2).slice(0, 1000));
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>📈 仪表盘</h2>
      <button onClick={loadDashboard} className="btn btn-secondary btn-sm" style={{ marginBottom: 16 }}>🔄 刷新</button>

      {loading ? (
        <div className="skeleton" style={{ height: 300, borderRadius: 12 }} />
      ) : error ? (
        <div style={{ padding: 20, color: "var(--danger)", background: "var(--danger-light)", borderRadius: 12 }}>
          ❌ {error}
        </div>
      ) : (
        <>
          {/* 空状态引导：所有数据均为空时显示 */}
          {!dashboard && !memoryStats && !learningStats && (
            <div style={{
              padding: 40, textAlign: "center",
              background: "var(--bg-primary)", borderRadius: 12,
              border: "1px dashed var(--border)", marginBottom: 24,
            }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>📊</div>
              <h3 style={{ margin: "0 0 8px", fontSize: 18 }}>暂无数据</h3>
              <p style={{ color: "var(--text-muted)", margin: "0 0 20px", fontSize: 14 }}>
                仪表盘将在你开始创作后显示以下数据：
              </p>
              <div style={{
                display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: 12, maxWidth: 720, margin: "0 auto", textAlign: "left",
              }}>
                <div style={{ padding: 16, background: "var(--bg-secondary)", borderRadius: 8 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>🎭 编排器状态</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>当前阶段、已生成章节、角色数量、进度百分比</div>
                </div>
                <div style={{ padding: 16, background: "var(--bg-secondary)", borderRadius: 8 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>🧠 记忆系统</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>上下文预算、已用 tokens、角色数、未回收线索</div>
                </div>
                <div style={{ padding: 16, background: "var(--bg-secondary)", borderRadius: 8 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>📚 学习引擎</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>总反馈数、风格编辑次数、学到的写作模式</div>
                </div>
              </div>
              <div style={{ marginTop: 24 }}>
                <button
                  onClick={() => window.dispatchEvent(new CustomEvent("navigate", { detail: { page: "orchestrator" } }))}
                  className="btn btn-primary"
                >
                  🚀 开始创作
                </button>
              </div>
            </div>
          )}

          {/* 编排器状态 */}
          {dashboard && (
            <div style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: 12, padding: 24, marginBottom: 24 }}>
              <h3 style={{ fontSize: 16, marginBottom: 16 }}>🎭 编排器状态</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
                {[
                  { label: "当前阶段", value: dashboard.stage },
                  { label: "已生成章节", value: `${dashboard.chapters_generated ?? 0}` },
                  { label: "角色数量", value: `${dashboard.characters_count ?? 0}` },
                  { label: "进度", value: `${Math.round((dashboard.progress || 0) * 100)}%` },
                ].map((item, i) => (
                  <div key={i}>
                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{item.label}</span>
                    <div style={{ fontSize: 18, fontWeight: 600 }}>{item.value ?? "-"}</div>
                  </div>
                ))}
              </div>
              <button onClick={runConsistency} className="btn btn-primary btn-sm" style={{ marginTop: 16 }}>🔍 一致性检查</button>
            </div>
          )}

          {/* 记忆系统统计 */}
          {memoryStats && (
            <div style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: 12, padding: 24, marginBottom: 24 }}>
              <h3 style={{ fontSize: 16, marginBottom: 16 }}>🧠 记忆系统</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
                {[
                  { label: "上下文预算", value: `${memoryStats.tokens_budget ?? 0} tokens` },
                  { label: "已用", value: `${memoryStats.tokens_used ?? 0} tokens` },
                  { label: "角色数", value: memoryStats.characters_count ?? 0 },
                  { label: "章节处理", value: memoryStats.chapters_processed ?? 0 },
                  { label: "未回收伏笔", value: memoryStats.unresolved_foreshadowing ?? 0 },
                ].map((item, i) => (
                  <div key={i}>
                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{item.label}</span>
                    <div style={{ fontSize: 18, fontWeight: 600 }}>{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 学习引擎统计 */}
          {learningStats && (
            <div style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: 12, padding: 24 }}>
              <h3 style={{ fontSize: 16, marginBottom: 16 }}>📚 学习引擎</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
                {[
                  { label: "总反馈数", value: learningStats.total_feedback ?? 0 },
                  { label: "风格编辑", value: learningStats.style_edits ?? 0 },
                  { label: "学到模式", value: learningStats.learned_patterns ?? 0 },
                ].map((item, i) => (
                  <div key={i}>
                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{item.label}</span>
                    <div style={{ fontSize: 18, fontWeight: 600 }}>{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
