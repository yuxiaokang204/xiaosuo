// 小说创作 Agent 系统 — 增强类型定义
// 与后端 Pydantic 模型对应，补充缺失的类型

// ──────────── 小说/章节相关 ────────────

export interface Novel {
  id: string;
  title: string;
  genre: string;
  outline?: string;
  status: 'drafting' | 'paused' | 'completed';
  chapter_count: number;
  current_word_count: number;
  target_word_count: number;
  world_id?: string;
  style_guide_id?: string;
  volumes?: Volume[];
  characters?: Character[];
  created_at: string;
  updated_at: string;
}

export interface NovelSummary {
  id: string;
  title: string;
  genre?: string;
  status?: string;
  current_word_count: number;
  target_word_count: number;
  updated_at: string;
}

export interface Volume {
  id: string;
  novel_id: string;
  title: string;
  description?: string;
  word_count: number;
  order: number;
}

export interface Chapter {
  id: string;
  volume_id: string;
  novel_id?: string;
  chapter_number?: number;
  title: string;
  outline?: string;
  content?: string;
  word_count: number;
  status: 'outlined' | 'drafted' | 'edited' | 'reviewed';
  characters_present: string[];
  locations: string[];
  foreshadowing: string[];
  callbacks: string[];
  order: number;
  created_at: string;
  updated_at: string;
}

// ──────────── 角色相关 ────────────

export interface Character {
  id: string;
  novel_id: string;
  name: string;
  aliases: string[];
  role: string;
  personality?: string;
  background?: string;
  goals: string[];
  conflicts: string[];
  speech_pattern?: string;
  appearance?: string;
  arc_data?: any;
  world_id?: string;
  // v6.0 角色代入式创作扩展字段
  psychological_profile?: any;
  behavior_tags?: string[];
  relationship_webs?: any[];
  speech_fingerprint?: any;
  first_appear_chapter?: number;
  last_appear_chapter?: number | null;
  character_status?: string;
}

// ──────────── 世界观相关 ────────────

export interface WorldSetting {
  id: string;
  novel_id: string;
  name: string;
  category: string;
  description?: string;
  rules: string[];
  history: any[];
  // v6.0 世界观扩展字段
  key_locations?: any[];
  factions?: any[];
  unique_appeal?: string;
}

// ──────────── 风格指南相关 ────────────

export interface StyleGuide {
  id: string;
  novel_id: string;
  vocabulary_preference: string[];
  sentence_patterns: string[];
  pacing_preference?: string;
  tone?: string;
  anti_patterns: string[];
  reference_works: string[];
  updated_at: string;
}

// ──────────── Agent/编排相关 ────────────

export interface AgentStatus {
  agent_id: string;
  agent_name: string;
  status: 'idle' | 'running' | 'completed' | 'error';
  progress: number;
  result?: any;
}

export interface OrchestratorState {
  novel_id: string;
  current_stage: string;
  stages: StageProgress[];
  active_agents: AgentStatus[];
  is_running: boolean;
}

export interface StageProgress {
  stage: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  progress: number;
  result?: any;
}

// ──────────── 记忆系统相关 ────────────

export interface MemoryStats {
  total_items_scored: number;
  tokens_budget: number;
  tokens_used: number;
  included_characters: number;
  included_world: number;
  included_summaries: number;
  included_foreshadowing: number;
  chapter_count: number;
}

export interface MemoryItem {
  id: string;
  novel_id: string;
  category: string;
  content: string;
  importance: number;
  created_at: string;
  refs: number;
}

// ──────────── 学习引擎相关 ────────────

export interface StyleFingerprint {
  user_id: string;
  preferred_words: Record<string, string[]>;
  sentence_patterns: string[];
  anti_patterns: string[];
  style_tags: Record<string, number>;
  edit_count: number;
}

export interface LearningStats {
  total_edits: number;
  style_adjustments: number;
  word_preferences: Record<string, number>;
  pattern_improvements: number;
}

// ──────────── LLM 配置相关 ────────────

export interface LLMConfig {
  id: string;
  provider: string;
  api_key?: string;
  model: string;
  api_base?: string;
  is_default: boolean;
  created_at: string;
}

export interface LLMProvider {
  id: string;
  label: string;
  description: string;
  api_base?: string;
  models: string[];
  needs_api_key: boolean;
}

// ──────────── 反馈/学习相关 ────────────

export interface ChapterFeedback {
  id: string;
  novel_id: string;
  chapter_id: string;
  feedback_type: 'style_edit' | 'character_edit' | 'deletion';
  original_text?: string;
  edited_text?: string;
  rating?: number;
  comment?: string;
  created_at: string;
}

// ──────────── 一致性检查相关 ────────────

export interface ConsistencyCheckResult {
  novel_id: string;
  chapter_id: string;
  issues: ConsistencyIssue[];
  overall_score: number;
  checked_at: string;
}

export interface ConsistencyIssue {
  type: 'character' | 'world' | 'timeline' | 'plot' | 'style';
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  suggestion?: string;
}

// ──────────── 叙事时间线相关 ────────────

export interface TimelineEvent {
  chapter: number;
  title: string;
  content?: string;
  characters: string[];
  location?: string;
  events: string[];
  foreshadowing?: string[];
}

// ──────────── 角色关系图谱相关 ────────────

export interface CharacterNode {
  id: string;
  name: string;
  role: string;
  color: string;
  description?: string;
}

export interface RelationshipEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

// ──────────── Prompt 管理相关 ────────────

export interface PromptTemplate {
  id: string;
  category: string;
  name: string;
  content: string;
  variables: string[];
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

// ──────────── 请求/响应模型 ────────────

export interface CreateNovelRequest {
  title: string;
  genre: string;
  target_word_count: number;
}

export interface OutlineRequest {
  theme: string;
  tone?: string;
  chapter_count?: number;
}

export interface DraftRequest {
  chapter_id: string;
  additional_context?: string;
}

export interface EditRequest {
  chapter_id: string;
  instructions?: string;
}

export interface ContinueRequest {
  chapter_id: string;
  word_count?: number;
}

export interface CreateVolumeRequest {
  title: string;
  description?: string;
  order: number;
}

export interface CreateCharacterRequest {
  name: string;
  role?: string;
  personality?: string;
  background?: string;
}

export interface CreateWorldSettingRequest {
  name: string;
  category?: string;
  description?: string;
}
