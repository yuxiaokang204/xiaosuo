/**
 * API Hooks — TanStack Query 封装
 * v5.3: 统一数据获取/缓存/自动刷新
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAppStore } from "../stores/appStore";

// ── 基础请求工具 ──

const BASE = "/api";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(`API ${r.status}: ${r.statusText}`);
  return r.json();
}

// ── 小说相关 ──

export function useNovels() {
  return useQuery({
    queryKey: ["novels"],
    queryFn: () => fetchJSON<{ novels: any[] }>(`${BASE}/novels`),
  });
}

export function useNovel(novelId: string | null) {
  return useQuery({
    queryKey: ["novel", novelId],
    queryFn: () => fetchJSON<any>(`${BASE}/novels/${novelId}`),
    enabled: !!novelId,
  });
}

export function useCreateNovel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: any) =>
      fetchJSON<any>(`${BASE}/novels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["novels"] }),
  });
}

export function useDeleteNovel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (novelId: string) =>
      fetch(`${BASE}/novels/${novelId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["novels"] }),
  });
}

// ── 章节相关 ──

export function useChapterContent(novelId: string | null, chapterId: string | null) {
  return useQuery({
    queryKey: ["chapter", novelId, chapterId],
    queryFn: () =>
      fetchJSON<any>(`${BASE}/novels/${novelId}/chapters/${chapterId}/content`),
    enabled: !!novelId && !!chapterId,
  });
}

export function useUpdateChapter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ novelId, chapterId, data }: { novelId: string; chapterId: string; data: any }) =>
      fetchJSON<any>(`${BASE}/novels/${novelId}/chapters/${chapterId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: (_, vars) =>
      qc.invalidateQueries({ queryKey: ["chapter", vars.novelId, vars.chapterId] }),
  });
}

// ── LLM 配置 ──

export function useLLMConfig() {
  return useQuery({
    queryKey: ["llm", "config"],
    queryFn: () => fetchJSON<any>(`${BASE}/llm/config`),
  });
}

export function useLLMConfigs() {
  return useQuery({
    queryKey: ["llm", "configs"],
    queryFn: () => fetchJSON<{ configs: any[] }>(`${BASE}/llm/configs`),
  });
}

export function useSetLLMConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: any) =>
      fetchJSON<any>(`${BASE}/llm/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["llm"] });
    },
  });
}

export function useSaveLLMConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: any) =>
      fetchJSON<any>(`${BASE}/llm/configs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm", "configs"] }),
  });
}

export function useDeleteLLMConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (configId: string) =>
      fetch(`${BASE}/llm/configs/${configId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["llm", "configs"] }),
  });
}

// ── Prompt 管理 ──

export function usePrompts(filters?: {
  agent_type?: string;
  depth_level?: number | null;
  prompt_type?: string;
  active_only?: boolean;
}) {
  const params = new URLSearchParams();
  if (filters?.agent_type) params.set("agent_type", filters.agent_type);
  if (filters?.depth_level !== null && filters?.depth_level !== undefined)
    params.set("depth_level", String(filters.depth_level));
  if (filters?.prompt_type) params.set("prompt_type", filters.prompt_type);
  if (filters?.active_only) params.set("active_only", "true");
  return useQuery({
    queryKey: ["prompts", filters],
    queryFn: () => fetchJSON<any>(`${BASE}/prompts?${params.toString()}`),
  });
}

export function useSeedPrompts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      fetchJSON<any>(`${BASE}/prompts/seed-defaults`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export function useSavePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: any) =>
      fetchJSON<any>(`${BASE}/prompts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export function useUpdatePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ promptId, data }: { promptId: string; data: any }) =>
      fetchJSON<any>(`${BASE}/prompts/${promptId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export function useDeletePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (promptId: string) =>
      fetch(`${BASE}/prompts/${promptId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export function useActivatePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (promptId: string) =>
      fetchJSON<any>(`${BASE}/prompts/${promptId}/activate`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

// ── 编排器 ──

export function useOrchestratorStatus(novelId: string | null) {
  return useQuery({
    queryKey: ["orchestrator", novelId],
    queryFn: () => fetchJSON<any>(`${BASE}/orchestrator/status`),
    enabled: !!novelId,
    refetchInterval: 5000,  // 每5秒轮询一次
  });
}

export function useOrchestratorDashboard(novelId: string | null) {
  return useQuery({
    queryKey: ["orchestrator", "dashboard", novelId],
    queryFn: () => fetchJSON<any>(`${BASE}/orchestrator/${novelId}/dashboard`),
    enabled: !!novelId,
    refetchInterval: 10000,
  });
}

// ── 学习引擎 ──

export function useLearningStats() {
  return useQuery({
    queryKey: ["learning", "stats"],
    queryFn: () => fetchJSON<any>(`${BASE}/learning/stats`),
  });
}

export function useSubmitFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: any) =>
      fetchJSON<any>(`${BASE}/learning/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["learning"] }),
  });
}

// ── 预设 ──

export function usePresets() {
  return useQuery({
    queryKey: ["presets"],
    queryFn: () => fetchJSON<any>(`${BASE}/presets`),
  });
}

export function useWorldSettings() {
  return useQuery({
    queryKey: ["settings", "world"],
    queryFn: () => fetchJSON<any>(`${BASE}/presets`),
  });
}

export function useCharacterSettings() {
  return useQuery({
    queryKey: ["settings", "character"],
    queryFn: () => fetchJSON<any>(`${BASE}/presets`),
  });
}

// ── 记忆系统 ──

export function useMemoryStats() {
  return useQuery({
    queryKey: ["memory", "stats"],
    queryFn: () => fetchJSON<any>(`${BASE}/memory/stats`),
  });
}

// ── 衔接引擎 ──

export function useContinuityStats(novelId: string | null) {
  return useQuery({
    queryKey: ["continuity", "stats", novelId],
    queryFn: () => fetchJSON<any>(`${BASE}/continuity/${novelId}/stats`),
    enabled: !!novelId,
  });
}

export function useSubmitContinuityFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ novelId, data }: { novelId: string; data: any }) =>
      fetchJSON<any>(`${BASE}/continuity/${novelId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: (_, vars) =>
      qc.invalidateQueries({ queryKey: ["continuity", "stats", vars.novelId] }),
  });
}