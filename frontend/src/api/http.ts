import axios from 'axios'
import { message } from 'ant-design-vue'

const http = axios.create({
  baseURL: '/api',
  // 请求超时（毫秒），可经 VITE_API_TIMEOUT 配置，默认 60s
  timeout: Number(import.meta.env.VITE_API_TIMEOUT) || 60000,
})

// 请求拦截：注入 Token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一错误处理
http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    // 登录请求的 401 是「账号/密码错误」，不应按「登录过期」处理，更不能跳转
    const isLoginRequest = (error.config?.url || '').includes('/auth/login')
    if (status === 401 && !isLoginRequest) {
      localStorage.removeItem('token')
      if (location.hash !== '#/login') {
        location.hash = '#/login'
      }
      message.error('登录已过期，请重新登录')
    } else {
      message.error(detail || error.message || '请求失败')
    }
    return Promise.reject(error)
  },
)

export default http
