import axios from 'axios'
import { message } from 'ant-design-vue'
import i18n from '@/i18n'

// 创建axios实例
const instance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 自动添加token
instance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 统一处理错误
instance.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    if (error.response) {
      switch (error.response.status) {
        case 401:
          // Token过期或无效
          message.error(i18n.global.t('auth.tokenExpired'))
          localStorage.removeItem('auth_token')
          localStorage.removeItem('user_info')
          window.location.href = '/login'
          break
        case 403:
          message.error(i18n.global.t('auth.noPermission'))
          break
        case 404:
          message.error(i18n.global.t('auth.resourceNotFound'))
          break
        case 500:
          message.error(i18n.global.t('auth.serverError'))
          break
        default:
          message.error(error.response.data?.detail || i18n.global.t('auth.requestFailed'))
      }
    } else if (error.request) {
      message.error(i18n.global.t('auth.networkError'))
    } else {
      message.error(i18n.global.t('auth.requestConfigError'))
    }
    return Promise.reject(error)
  }
)

export default instance
