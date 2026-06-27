import React, { useState, useMemo, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./Layout";

// 页面组件
import { OverviewPage } from "./pages/OverviewPage";
import { OrchestratorPage } from "./pages/OrchestratorPage";
import { NovelManagerPage } from "./pages/NovelManagerPage";
import { NovelReadPage } from "./pages/NovelReadPage";
import { StandaloneEditPage } from "./pages/StandaloneEditPage";
import { CharactersPage } from "./pages/CharactersPage";
import { WorldPage } from "./pages/WorldPage";
import { SemanticSearchPage } from "./pages/SemanticSearchPage";
import { LearningPage } from "./pages/LearningPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LLMConfigPage } from "./pages/LLMConfigPage";
import { StandaloneDraftPage } from "./pages/StandaloneDraftPage";
import { PromptManagerPage } from "./pages/PromptManagerPage";
// 工具组件
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./index.css";

// v5.3: TanStack Query 客户端
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,  // 5分钟缓存
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

const PAGE_COMPONENTS: Record<string, React.FC> = {
  overview: OverviewPage,
  orchestrator: OrchestratorPage,
  novels: NovelManagerPage,
  read: NovelReadPage,
  edit: StandaloneEditPage,
  draft: StandaloneDraftPage,
  characters: CharactersPage,
  world: WorldPage,
  search: SemanticSearchPage,
  learning: LearningPage,
  dashboard: DashboardPage,
  llm: LLMConfigPage,
  prompts: PromptManagerPage,
};

type PageId = keyof typeof PAGE_COMPONENTS;

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<PageId>("overview");
  const [currentNovelTitle, setCurrentNovelTitle] = useState("");

  // 监听页面内导航事件
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      const page = detail?.page;
      if (page && page in PAGE_COMPONENTS) {
        setCurrentPage(page as PageId);
      }
      if (detail?.novelTitle) {
        setCurrentNovelTitle(detail.novelTitle);
      }
    };
    window.addEventListener("navigate", handler);
    return () => window.removeEventListener("navigate", handler);
  }, []);

  // 监听小说标题更新事件
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.title !== undefined) {
        setCurrentNovelTitle(detail.title);
      }
    };
    window.addEventListener("novel-title", handler);
    return () => window.removeEventListener("novel-title", handler);
  }, []);

  const CurrentPage = useMemo(() => {
    return PAGE_COMPONENTS[currentPage];
  }, [currentPage]);

  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <Layout
          currentPage={currentPage}
          onNavigate={(page) => setCurrentPage(page as PageId)}
          currentNovelTitle={currentNovelTitle}
        >
          <ErrorBoundary key={currentPage}>
            <CurrentPage />
          </ErrorBoundary>
        </Layout>
      </ErrorBoundary>
    </QueryClientProvider>
  );
};

export default App;
