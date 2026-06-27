/**
 * useOrchestrator — 编排器 SSE hook
 * 封装编排器运行状态和流式事件
 */
import { useState, useCallback } from "react";
import { useSSE } from "./useSSE";

export interface OrchestratorEvent {
  event: string;
  data: any;
}

interface UseOrchestratorReturn {
  events: OrchestratorEvent[];
  currentStage: string;
  currentChapter: number;
  totalChapters: number;
  isRunning: boolean;
  error: string | null;
  streamUrl: string | null;
  startStream: (title: string, theme: string, tone: string, chapterCount: number) => void;
  stopStream: () => void;
  clearEvents: () => void;
}

export function useOrchestrator(): UseOrchestratorReturn {
  const [events, setEvents] = useState<OrchestratorEvent[]>([]);
  const [currentStage, setCurrentStage] = useState("");
  const [currentChapter, setCurrentChapter] = useState(0);
  const [totalChapters, setTotalChapters] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);

  const handleSSEEvent = useCallback((eventName: string, data: any) => {
    const event: OrchestratorEvent = { event: eventName, data };
    setEvents((prev) => [...prev.slice(-99), event]);

    if (eventName === "stage_start") {
      setCurrentStage(data.stage || "");
    } else if (eventName === "chapter_start") {
      setCurrentChapter(data.index || 0);
      setTotalChapters(data.total || 0);
    } else if (eventName === "chapter_done") {
      setCurrentChapter(0);
    } else if (eventName === "stage_error") {
      setError(data.error || "阶段执行出错");
      setIsRunning(false);
    } else if (eventName === "run_all_done" || eventName === "run_all_aborted") {
      setIsRunning(false);
    }
  }, []);

  const startStream = useCallback(
    (title: string, theme: string, tone: string = "史诗", chapterCount: number = 5) => {
      const params = new URLSearchParams({
        title, theme, tone, chapter_count: String(chapterCount),
      });
      const url = `/api/orchestrator/stream?${params.toString()}`;
      setStreamUrl(url);
      setIsRunning(true);
      setError(null);
      setEvents([]);
    },
    []
  );

  const stopStream = useCallback(() => {
    setIsRunning(false);
    setStreamUrl(null);
  }, []);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  useSSE(streamUrl || "", {
    onEvent: handleSSEEvent,
    onConnect: () => setIsRunning(true),
    onDisconnect: () => setIsRunning(false),
    onError: () => {
      setError("SSE 连接错误");
      setIsRunning(false);
    },
    autoReconnect: false,
  });

  return {
    events, currentStage, currentChapter, totalChapters,
    isRunning, error, streamUrl, startStream, stopStream, clearEvents,
  };
}
