/**
 * 前端全局状态管理 — Zustand + TanStack Query
 * v5.3: 统一状态管理，替代各页面独立 useState
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ── 类型定义 ──

export interface NovelInfo {
  id: string;
  title: string;
  theme: string;
  tone: string;
  genre: string;
  status: string;
  chapter_count: number;
  platform: string;
  word_count: number;
  created_at: string;
}

export interface ChapterInfo {
  id: string;
  novel_id: string;
  title: string;
  index: number;
  word_count: number;
  status: string;
}

export interface LLMConfig {
  provider: string;
  api_key: string;
  model: string;
  api_base: string;
  is_default: boolean;
}

// ── 应用级全局状态 ──

interface AppState {
  // 当前选中小说
  currentNovelId: string | null;
  currentNovel: NovelInfo | null;
  setCurrentNovel: (novel: NovelInfo | null) => void;

  // 章节列表缓存
  chapters: ChapterInfo[];
  setChapters: (chapters: ChapterInfo[]) => void;

  // LLM 配置
  llmConfig: LLMConfig | null;
  setLLMConfig: (config: LLMConfig | null) => void;

  // 编排器运行状态
  orchestratorRunning: boolean;
  setOrchestratorRunning: (running: boolean) => void;

  // 侧边栏
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentNovelId: null,
      currentNovel: null,
      setCurrentNovel: (novel) => set({ currentNovel: novel, currentNovelId: novel?.id || null }),

      chapters: [],
      setChapters: (chapters) => set({ chapters }),

      llmConfig: null,
      setLLMConfig: (config) => set({ llmConfig: config }),

      orchestratorRunning: false,
      setOrchestratorRunning: (running) => set({ orchestratorRunning: running }),

      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    {
      name: 'novel-agent-app-store',
      partialize: (state) => ({
        currentNovelId: state.currentNovelId,
        currentNovel: state.currentNovel,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
    }
  )
);