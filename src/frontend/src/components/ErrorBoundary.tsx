/**
 * ErrorBoundary — React 错误边界组件
 */
import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = { hasError: false, error: null };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.props.onError?.(error, errorInfo);
    console.error("[ErrorBoundary]", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div style={{
          padding: 24, margin: 16,
          background: "var(--danger-light)",
          border: "1px solid var(--danger)",
          borderRadius: 12,
          color: "var(--danger)",
        }}>
          <h3 style={{ marginTop: 0 }}>组件渲染出错</h3>
          <p style={{ fontSize: 14, fontFamily: "monospace" }}>
            {this.state.error?.message}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              marginTop: 12, padding: "8px 16px",
              background: "var(--danger)", color: "#fff",
              border: "none", borderRadius: 6, cursor: "pointer",
            }}
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
