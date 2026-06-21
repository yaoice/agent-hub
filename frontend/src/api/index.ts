import http from './http'
import type {
  ConversationAppOption,
  ConversationPage,
  ConversationQuery,
  ConversationStats,
  ConversationSyncPayload,
  ConversationSyncResult,
  DashboardResponse,
  LoginResponse,
  Project,
  ProjectForm,
  ProjectMember,
  Provider,
  SyncJob,
  SyncPayload,
  SyncResult,
  UserCreateForm,
  UserDetail,
  UserInfo,
  UserRow,
  UserUpdateForm,
} from '@/types'

export const authApi = {
  login(username: string, password: string) {
    const body = new URLSearchParams()
    body.append('username', username)
    body.append('password', password)
    return http
      .post<LoginResponse>('/auth/login', body, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      .then((r) => r.data)
  },
  me() {
    return http.get<UserInfo>('/auth/me').then((r) => r.data)
  },
}

export const userApi = {
  list(search?: string) {
    return http.get<UserRow[]>('/users', { params: { search } }).then((r) => r.data)
  },
  detail(id: number) {
    return http.get<UserDetail>(`/users/${id}`).then((r) => r.data)
  },
  create(data: UserCreateForm) {
    return http.post<UserRow>('/users', data).then((r) => r.data)
  },
  update(id: number, data: UserUpdateForm) {
    return http.put<UserRow>(`/users/${id}`, data).then((r) => r.data)
  },
  setStatus(id: number, isActive: boolean) {
    return http
      .patch<UserRow>(`/users/${id}/status`, { is_active: isActive })
      .then((r) => r.data)
  },
}

export const providerApi = {
  list() {
    return http.get<Provider[]>('/providers').then((r) => r.data)
  },
  setEnabled(typeKey: string, enabled: boolean) {
    return http.patch<Provider>(`/providers/${typeKey}`, { enabled }).then((r) => r.data)
  },
}

export const projectApi = {
  list() {
    return http.get<Project[]>('/projects').then((r) => r.data)
  },
  create(data: ProjectForm) {
    return http.post<Project>('/projects', data).then((r) => r.data)
  },
  update(id: number, data: Partial<ProjectForm>) {
    return http.put<Project>(`/projects/${id}`, data).then((r) => r.data)
  },
  remove(id: number) {
    return http.delete(`/projects/${id}`)
  },
  sync(id: number, payload?: SyncPayload) {
    return http.post<SyncResult>(`/projects/${id}/sync`, payload || {}).then((r) => r.data)
  },
  members(id: number) {
    return http.get<ProjectMember[]>(`/projects/${id}/members`).then((r) => r.data)
  },
  addMember(id: number, userId: number, projectRole: string) {
    return http
      .post<ProjectMember>(`/projects/${id}/members`, {
        user_id: userId,
        project_role: projectRole,
      })
      .then((r) => r.data)
  },
  removeMember(id: number, userId: number) {
    return http.delete(`/projects/${id}/members/${userId}`)
  },
}

export const dashboardApi = {
  fetch(projectId?: number) {
    return http
      .get<DashboardResponse>('/dashboard', { params: { project_id: projectId } })
      .then((r) => r.data)
  },
}

export const conversationApi = {
  list(projectId: number, query: ConversationQuery = {}) {
    return http
      .get<ConversationPage>(`/projects/${projectId}/conversations`, { params: query })
      .then((r) => r.data)
  },
  apps(projectId: number) {
    return http
      .get<ConversationAppOption[]>(`/projects/${projectId}/conversation-apps`)
      .then((r) => r.data)
  },
  stats(projectId: number, query: ConversationQuery = {}) {
    return http
      .get<ConversationStats>(`/projects/${projectId}/conversation-stats`, { params: query })
      .then((r) => r.data)
  },
  sync(projectId: number, payload?: ConversationSyncPayload) {
    return http
      .post<ConversationSyncResult>(`/projects/${projectId}/sync-conversations`, payload || {})
      .then((r) => r.data)
  },
  // 启动异步同步任务，返回任务对象（用于轮询）
  startSyncJob(projectId: number, payload?: ConversationSyncPayload) {
    return http
      .post<SyncJob>(`/projects/${projectId}/conversation-sync-jobs`, payload || {})
      .then((r) => r.data)
  },
  // 查询指定同步任务进度
  getSyncJob(projectId: number, jobId: number) {
    return http
      .get<SyncJob>(`/projects/${projectId}/conversation-sync-jobs/${jobId}`)
      .then((r) => r.data)
  },
  // 获取最近一次同步任务（进入页面时恢复进度），无则返回 null
  latestSyncJob(projectId: number) {
    return http
      .get<SyncJob | null>(`/projects/${projectId}/conversation-sync-jobs/latest`)
      .then((r) => r.data)
  },
  // 请求终止进行中的同步任务
  cancelSyncJob(projectId: number, jobId: number) {
    return http
      .post<SyncJob>(`/projects/${projectId}/conversation-sync-jobs/${jobId}/cancel`)
      .then((r) => r.data)
  },
}
