/**
 * useNovels — 小说数据管理 hook
 */
import { useState, useCallback, useEffect } from "react";
import { api } from "../api";

export interface NovelSummary {
  id: string;
  title: string;
  genre?: string;
  status?: string;
  current_word_count?: number;
  target_word_count?: number;
  updated_at?: string;
}

interface UseNovelsReturn {
  novels: NovelSummary[];
  loading: boolean;
  error: string | null;
  fetchNovels: () => Promise<void>;
  createNovel: (title: string, genre: string) => Promise<any>;
  deleteNovel: (id: string) => Promise<void>;
  updateChapter: (novelId: string, chapterId: string, content: string) => Promise<void>;
}

export function useNovels(): UseNovelsReturn {
  const [novels, setNovels] = useState<NovelSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchNovels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getNovels();
      setNovels(data.novels || []);
    } catch (e: any) {
      setError(e.message || "获取小说列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const createNovel = useCallback(async (title: string, genre: string) => {
    try {
      const data = await api.createNovel(title, genre);
      setNovels((prev) => [...prev, data]);
      return data;
    } catch (e: any) {
      setError(e.message || "创建小说失败");
      throw e;
    }
  }, []);

  const deleteNovel = useCallback(async (id: string) => {
    try {
      await api.delete(`/api/novels/${id}`);
      setNovels((prev) => prev.filter((n) => n.id !== id));
    } catch (e: any) {
      setError(e.message || "删除小说失败");
      throw e;
    }
  }, []);

  const updateChapter = useCallback(async (novelId: string, chapterId: string, content: string) => {
    try {
      await api.put(`/api/novels/${novelId}/chapters/${chapterId}`, { content });
    } catch (e: any) {
      setError(e.message || "保存章节失败");
      throw e;
    }
  }, []);

  useEffect(() => {
    fetchNovels();
  }, [fetchNovels]);

  return { novels, loading, error, fetchNovels, createNovel, deleteNovel, updateChapter };
}
