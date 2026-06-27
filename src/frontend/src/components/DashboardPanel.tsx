/**
 * 仪表盘面板
 * 参考: AI_NovelGenerator 的目录可视化 + Webnovel Writer 的 /webnovel-dashboard
 * 展示: 全局摘要、角色状态、伏笔进度、一致性审查结果
 */
import React, { useEffect, useState } from "react";

interface DashboardData {
  novel_id: string;
  title: string;
  stage: string;
  completed_stages: string[];
  paused: boolean;
  chapter_count: number;
  state_tracker: {
    characters: Record<string, any>;
    foreshadowings: any[];
    chapter_count: number;
  };
  global_summary: {
    total_chapters: number;
    summaries: any[];
    plot_progress: { phase: string; total_words: number; avg_quality: number };
  };
  consistency_issues: {
    total: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
    issues: any[];
  };
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#dc2626",
  error: "#ef4444",
  warning: "#f59e0b",
  info: "#3b82f6",
};

const SEVERITY_LABELS: Record<string, string> = {
  critical: "严重",
  error: "错误",
  warning: "警告",
  info: "提示",
};

const TYPE_LABELS: Record<string, string> = {
  plot_contradiction: "剧情矛盾",
  character_ooc: "角色OOC",
  world_conflict: "世界观冲突",
  logic_gap: "逻辑断层",
  timeline: "时间线",
};

export const DashboardPanel: React.FC = () => {
  const [novelId, setNovelId] = useState("");
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [checkChapter, setCheckChapter] = useState(1);
  const [checkResult, setCheckResult] = useState<any>(null);
  const [activeList, setActiveList] = useState<string[]>([]);

  useEffect(() => {
    // 自动获取活跃编排器列表
    fetch("/api/orchestrator/list").then(r => r.json()).then(d => {
      const list = d.orchestrators || [];
      if (list.length > 0) {
        setNovelId(list[0].novel_id);
        setActiveList(list.map((o: any) => o.novel_id));
      }
    }).catch(() => {});
  }, []);

  const loadDashboard = () => {
    if (!novelId) return;
    setLoading(true);
    fetch(`/api/orchestrator/${novelId}/dashboard`)
      .then(r => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  const runCheck = () => {
    setChecking(true);
    fetch(`/api/orchestrator/${novelId}/check-consistency?chapter_idx=${checkChapter}`, { method: "POST" })
      .then(r => r.json())
      .then(setCheckResult)
      .catch(() => setCheckResult(null))
      .finally(() => setChecking(false));
  };

  const ds = data?.state_tracker;
  const gs = data?.global_summary;
  const ci = data?.consistency_issues;

  return (
    <div>
      {/* 顶部工具栏 */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16, alignItems: "center", flexWrap: "wrap" }}>
        <select value={novelId} onChange={e => setNovelId(e.target.value)}
          style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 14 }}>
          <option value="">-- 选择小说 --</option>
          {activeList.map(id => <option key={id} value={id}>{id}</option>)}
        </select>
        <button onClick={loadDashboard}
          style={{ padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 14 }}>
          📊 加载仪表盘
        </button>
        <span style={{ fontSize: 13, color: "#6b7280" }}>
          {data ? `《${data.title}》- ${data.stage}` : "未加载"}
        </span>
      </div>

      {loading && <div style={{ textAlign: "center", padding: 40, color: "#9ca3af" }}>加载中...</div>}

      {data && (
        <>
          {/* 概览卡片 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 20 }}>
            <StatCard label="总章节" value={`${gs?.total_chapters || 0} / ${data.chapter_count}`} icon="📖" />
            <StatCard label="情节阶段" value={gs?.plot_progress?.phase || "-"} icon="🎯" />
            <StatCard label="总字数" value={gs?.plot_progress?.total_words?.toLocaleString() || "0"} icon="📝" />
            <StatCard label="平均质量" value={gs?.plot_progress?.avg_quality?.toFixed(1) || "-"} icon="⭐" />
            <StatCard label="角色数" value={Object.keys(ds?.characters || {}).length} icon="👥" />
            <StatCard label="伏笔进度" value={`${Object.values(ds?.foreshadowings || {}).filter((f: any) => f.status === "resolved").length}/${Object.keys(ds?.foreshadowings || {}).length}`} icon="🔮" />
          </div>

          {/* 一致性审查 */}
          <Section title="一致性审查">
            {ci && ci.total > 0 ? (
              <div>
                <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
                  {Object.entries(ci.by_severity || {}).map(([s, c]) => (
                    <span key={s} style={{
                      padding: "2px 10px", borderRadius: 12, fontSize: 12,
                      background: SEVERITY_COLORS[s] + "20", color: SEVERITY_COLORS[s],
                      fontWeight: 600,
                    }}>
                      {SEVERITY_LABELS[s] || s}: {c}
                    </span>
                  ))}
                </div>
                {(ci.issues || []).slice(0, 10).map((issue: any, i: number) => (
                  <div key={i} style={{
                    padding: "8px 12px", marginBottom: 6, borderRadius: 6, fontSize: 13,
                    background: "#fef2f2", borderLeft: `3px solid ${SEVERITY_COLORS[issue.severity] || "#ef4444"}`,
                  }}>
                    <span style={{ fontWeight: 600, marginRight: 6 }}>
                      [{TYPE_LABELS[issue.type] || issue.type}]
                    </span>
                    {issue.description}
                    {issue.suggestion && <span style={{ color: "#6b7280", marginLeft: 8 }}>→ {issue.suggestion}</span>}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: "#10b981", fontSize: 14, padding: 8 }}>未检测到一致性问题</div>
            )}
            {/* 手动审查 */}
            <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ fontSize: 13 }}>审查章节:</span>
              <input type="number" min={1} max={gs?.total_chapters || 1} value={checkChapter}
                onChange={e => setCheckChapter(parseInt(e.target.value) || 1)}
                style={{ width: 60, padding: "4px 8px", borderRadius: 4, border: "1px solid #d1d5db" }} />
              <button onClick={runCheck} disabled={checking}
                style={{ padding: "6px 12px", background: "#f59e0b", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
                {checking ? "审查中..." : "🔍 手动审查"}
              </button>
            </div>
            {checkResult && (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>
                  第{checkResult.chapter}章《{checkResult.title}》: {checkResult.total_issues}个问题
                </div>
                {(checkResult.issues || []).map((issue: any, i: number) => (
                  <div key={i} style={{
                    padding: "4px 8px", fontSize: 12, color: SEVERITY_COLORS[issue.severity], background: "#fef2f2",
                    borderRadius: 4, marginTop: 4,
                  }}>
                    [{TYPE_LABELS[issue.type] || issue.type}] {issue.description}
                  </div>
                ))}
              </div>
            )}
          </Section>

          {/* 章节摘要链 */}
          <Section title="章节摘要链">
            {(gs?.summaries || []).slice(-10).map((s: any) => (
              <div key={s.chapter} style={{
                padding: "8px 12px", marginBottom: 4, borderRadius: 6,
                background: "#f9fafb", fontSize: 13, lineHeight: 1.6,
              }}>
                <span style={{ fontWeight: 600 }}>第{s.chapter}章《{s.title}》</span>
                <span style={{ color: "#9ca3af", marginLeft: 8 }}>{s.word_count?.toLocaleString()}字</span>
                <div style={{ color: "#6b7280", marginTop: 2 }}>{s.summary}</div>
              </div>
            )) || <div style={{ color: "#9ca3af", fontSize: 13 }}>暂无摘要</div>}
          </Section>

          {/* 角色状态 */}
          <Section title="角色状态">
            {Object.entries(ds?.characters || {}).length > 0 ? (
              Object.entries(ds!.characters).map(([name, state]: [string, any]) => (
                <div key={name} style={{
                  padding: "8px 12px", marginBottom: 6, borderRadius: 6,
                  background: state.role === "protagonist" ? "#eff6ff" : "#f3f4f6",
                  borderLeft: `3px solid ${state.role === "protagonist" ? "#3b82f6" : "#9ca3af"}`,
                  fontSize: 13,
                }}>
                  <span style={{ fontWeight: 600 }}>{name}</span>
                  <span style={{ color: "#6b7280", marginLeft: 6 }}>
                    ({state.role === "protagonist" ? "主角" : state.role || "配角"})
                  </span>
                  <div style={{ color: "#4b5563", marginTop: 4, lineHeight: 1.6 }}>
                    {state.location && <span>📍 {state.location} </span>}
                    {state.physical && <span>💪 {state.physical} </span>}
                    {state.emotional && <span>💭 {state.emotional} </span>}
                    {state.power && <span>⚡ {state.power} </span>}
                  </div>
                  {state.items?.length > 0 && (
                    <div style={{ color: "#92400e", fontSize: 12, marginTop: 2 }}>
                      🎒 {state.items.join(", ")}
                    </div>
                  )}
                  {state.goals?.length > 0 && (
                    <div style={{ color: "#047857", fontSize: 12, marginTop: 2 }}>
                      🎯 {state.goals.join(", ")}
                    </div>
                  )}
                </div>
              ))
            ) : <div style={{ color: "#9ca3af", fontSize: 13 }}>暂未注册角色状态</div>}
          </Section>

          {/* 伏笔进度 */}
          <Section title="伏笔进度">
            {Object.keys(ds?.foreshadowings || {}).length > 0 ? (
              Object.entries(ds!.foreshadowings).map(([fid, f]: [string, any]) => (
                <div key={fid} style={{
                  padding: "6px 12px", marginBottom: 4, borderRadius: 6, fontSize: 13,
                  background: f.status === "resolved" ? "#f0fdf4" : "#fffbeb",
                  borderLeft: `3px solid ${f.status === "resolved" ? "#10b981" : "#f59e0b"}`,
                }}>
                  <span style={{ fontWeight: 600 }}>
                    {f.status === "resolved" ? "✅" : f.status === "developing" ? "🔄" : "🌱"}
                  </span>
                  <span style={{ marginLeft: 6 }}>第{f.chapter_planted}章埋下</span>
                  <span style={{ color: "#6b7280", marginLeft: 6 }}>[{f.type}]</span>
                  <span> {f.description}</span>
                  {f.status === "resolved" && <span style={{ color: "#10b981", marginLeft: 6 }}>已回收(第{f.chapter_resolved}章)</span>}
                </div>
              ))
            ) : <div style={{ color: "#9ca3af", fontSize: 13 }}>暂无伏笔记录</div>}
          </Section>
        </>
      )}
    </div>
  );
};

// ── 子组件 ──

const StatCard: React.FC<{ label: string; value: string | number; icon: string }> = ({ label, value, icon }) => (
  <div style={{
    padding: "16px", borderRadius: 10, background: "#fff",
    border: "1px solid #e5e7eb", textAlign: "center",
  }}>
    <div style={{ fontSize: 24 }}>{icon}</div>
    <div style={{ fontSize: 22, fontWeight: 700, color: "#1f2937", marginTop: 4 }}>{value}</div>
    <div style={{ fontSize: 12, color: "#9ca3af" }}>{label}</div>
  </div>
);

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div style={{
    marginBottom: 20, padding: 16, borderRadius: 10,
    background: "#fff", border: "1px solid #e5e7eb",
  }}>
    <div style={{ fontSize: 16, fontWeight: 700, color: "#1f2937", marginBottom: 12 }}>{title}</div>
    {children}
  </div>
);