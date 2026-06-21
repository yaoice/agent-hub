// 全局类型定义
export interface ProjectBrief {
  id: number
  name: string
  provider_type_key: string
  project_role: string | null
}

export interface UserInfo {
  id: number
  username: string
  role: string
  is_active: boolean
  projects: ProjectBrief[]
}

export interface LoginResponse {
  access_token: string
  token_type: string
  username: string
  role: string
}

// ---------- 用户管理 ----------
export interface UserRow {
  id: number
  username: string
  role: string
  is_active: boolean
  created_at: string
  project_count: number
}

export interface UserMembership {
  project_id: number
  project_name: string
  project_role: string
}

export interface UserDetail extends UserRow {
  memberships: UserMembership[]
}

export interface UserCreateForm {
  username: string
  password: string
  role: string
}

export interface UserUpdateForm {
  role?: string
  password?: string
  current_password?: string
  confirm_password?: string
}

// ---------- Provider 类型目录 ----------
export interface Provider {
  id: number
  type_key: string
  display_name: string
  enabled: boolean
  implemented: boolean
  description: string
}

// ---------- 项目 ----------
export interface Project {
  id: number
  name: string
  provider_type_key: string
  provider_display_name: string
  host: string
  region: string
  is_active: boolean
  secret_id_masked: string
  secret_key_masked: string
  member_count: number
  last_sync_at: string | null
  last_sync_source: string | null
  created_at: string
  updated_at: string
}

export interface ProjectForm {
  name: string
  provider_type_key: string
  host: string
  region: string
  is_active: boolean
  secret_id: string
  secret_key: string
}

export interface ProjectMember {
  id: number
  user_id: number
  username: string
  project_role: string
  created_at: string
}

export type SyncScope = 'app_count' | 'token' | 'conversations'

export interface SyncPayload {
  scopes?: SyncScope[]
  conv_begin?: string
  conv_end?: string
  max_records_per_app?: number
}

export interface SyncResult {
  ok: boolean
  source: string
  message: string
  synced_at: string
  scopes?: string[]
  details?: Record<string, any>
}

// ---------- 对话记录 ----------
export interface ConversationItem {
  id: number
  app_biz_id: string
  session_id: string
  user_biz_id: string
  user_nickname: string
  question: string
  answer: string
  intent_category: string
  create_time: string
  synced_at: string
}

export interface ConversationPage {
  total: number
  items: ConversationItem[]
}

export interface ConversationQuery {
  app_biz_id?: string
  begin?: string
  end?: string
  keyword?: string
  intent?: string
  limit?: number
  offset?: number
}

export interface ConversationSyncResult {
  source: string
  app_count: number
  fetched: number
  inserted: number
  message: string
  synced_at: string
}

export interface TrendPoint {
  date: string
  count: number
}

export interface IntentSlice {
  name: string
  count: number
}

export interface ConversationStats {
  trend: TrendPoint[]
  intents: IntentSlice[]
  total: number
}

// ---------- 看板 ----------
export interface AppEntry {
  name: string
  status: string
  app_biz_id?: string
}

export interface SpaceRow {
  space_id: string
  space_name: string
  app_count: number
  running: number
  offline: number
  apps: AppEntry[]
}

export interface Overview {
  total_spaces: number
  active_spaces: number
  empty_spaces: number
  total_apps: number
  running: number
  offline: number
}

export interface TokenItem {
  name: string
  value: number
  percentage: number
}

export interface DashboardData {
  overview: Overview
  spaces: SpaceRow[]
  token_top: {
    space: TokenItem[]
    app: TokenItem[]
    model: TokenItem[]
  }
}

export interface DashboardResponse {
  project_id: number
  project_name: string
  source: 'live' | 'mock'
  updated_at: string | null
  data: DashboardData
}
