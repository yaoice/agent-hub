import axios from 'axios'
import { message } from 'ant-design-vue'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
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
    if (status === 401) {
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
