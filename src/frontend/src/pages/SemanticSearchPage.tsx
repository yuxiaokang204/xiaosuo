/**
 * SemanticSearchPage — 语义搜索页
 */
import React, { useState } from "react";

export const SemanticSearchPage: React.FC = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`/api/orchestrator/memory-search?query=${encodeURIComponent(query)}`);
      const data = await r.json();
      setResults(data.results || data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: 22 }}>🔍 语义搜索</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="搜索记忆系统中的内容..."
          className="input"
          style={{ maxWidth: 400 }}
        />
        <button onClick={search} disabled={loading} className="btn btn-primary">
          {loading ? "搜索中..." : "搜索"}
        </button>
      </div>

      {error && (
        <div style={{ padding: 16, background: "var(--danger-light)", borderRadius: 8, color: "var(--danger)" }}>
          ❌ {error}
        </div>
      )}

      {results.length > 0 ? (
        <div style={{ display: "grid", gap: 12 }}>
          {results.map((r: any, i: number) => (
            <div key={i} className="card">
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <div>
                  <span className="badge badge-info" style={{ marginBottom: 8, display: "inline-block" }}>
                    {r.tag || "记忆项"}
                  </span>
                  <p style={{ fontSize: 14, margin: "8px 0" }}>{r.content || r.description || JSON.stringify(r)}</p>
                  {r.similarity !== undefined && (
                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      相似度: {r.similarity}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : !loading && !error ? (
        <div style={{ padding: 40, textAlign: "center", color: "var(--text-muted)", background: "var(--bg-primary)", borderRadius: 12 }}>
          输入关键词搜索记忆系统中的内容
        </div>
      ) : null}
    </div>
  );
};
