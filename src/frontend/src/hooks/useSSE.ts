/**
 * useSSE — 通用 SSE (Server-Sent Events) hook
 * 处理 SSE 连接、重连、事件分发
 */
import { useEffect, useRef, useCallback, useState } from "react";

interface SSEOptions {
  onEvent?: (event: string, data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
}

export function useSSE(url: string, options: SSEOptions = {}) {
  const {
    onEvent,
    onConnect,
    onDisconnect,
    onError,
    autoReconnect = true,
    maxReconnectAttempts = 3,
  } = options;

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isMountedRef = useRef(true);
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    if (!isMountedRef.current || !autoReconnect) return;

    try {
      const es = new EventSource(url);

      es.onopen = () => {
        if (!isMountedRef.current) return;
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        onConnect?.();
      };

      es.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          onEvent?.(data.event || "message", data.data);
        } catch {
          onEvent?.("message", event.data);
        }
      };

      es.addEventListener("chapter_token", (event) => {
        onEvent?.("chapter_token", JSON.parse((event as MessageEvent).data));
      });

      es.addEventListener("stage_start", (event) => {
        onEvent?.("stage_start", JSON.parse((event as MessageEvent).data));
      });

      es.addEventListener("chapter_start", (event) => {
        onEvent?.("chapter_start", JSON.parse((event as MessageEvent).data));
      });

      es.addEventListener("chapter_done", (event) => {
        onEvent?.("chapter_done", JSON.parse((event as MessageEvent).data));
      });

      es.addEventListener("drafting_done", (event) => {
        onEvent?.("drafting_done", JSON.parse((event as MessageEvent).data));
      });

      es.addEventListener("pipeline_start", (event) => {
        onEvent?.("pipeline_start", JSON.parse((event as MessageEvent).data));
      });

      es.addEventListener("pipeline_step", (event) => {
        onEvent?.("pipeline_step", JSON.parse((event as MessageEvent).data));
      });

      es.addEventListener("pipeline_done", (event) => {
        onEvent?.("pipeline_done", JSON.parse((event as MessageEvent).data));
      });

      es.addEventListener("stage_error", (event) => {
        onEvent?.("stage_error", JSON.parse((event as MessageEvent).data));
      });

      es.onerror = (event) => {
        if (!isMountedRef.current) return;
        setIsConnected(false);

        if (es.readyState === EventSource.CLOSED) {
          // 连接已关闭，不再重连
          onDisconnect?.();
          return;
        }

        // 尝试重连
        if (autoReconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          setTimeout(() => {
            if (isMountedRef.current) {
              es.close();
              connect();
            }
          }, 2000 * reconnectAttemptsRef.current);
        } else {
          onError?.(event);
        }
      };

      eventSourceRef.current = es;
    } catch (err) {
      onError?.(err as Event);
    }
  }, [url, autoReconnect, maxReconnectAttempts, onEvent, onConnect, onDisconnect, onError]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      disconnect();
    };
  }, [connect, disconnect]);

  return { isConnected, disconnect };
}
