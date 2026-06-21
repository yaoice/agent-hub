import { defineStore } from 'pinia'
import { authApi } from '@/api'
import type { ProjectBrief, UserInfo } from '@/types'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null as UserInfo | null,
  }),
  getters: {
    isAuthenticated: (s) => !!s.token,
    isAdmin: (s) => s.user?.role === 'admin',
    visibleProjects: (s): ProjectBrief[] => s.user?.projects || [],
  },
  actions: {
    async login(username: string, password: string) {
      const res = await authApi.login(username, password)
      this.token = res.access_token
      localStorage.setItem('token', res.access_token)
      // 登录后拉取完整用户信息（含可见项目）
      await this.fetchMe()
    },
    async fetchMe() {
      if (!this.token) return
      this.user = await authApi.me()
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
    },
  },
})
