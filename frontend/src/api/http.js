import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 12000
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('opinion_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error?.response?.data?.message || error?.message || '接口请求失败'
    if (import.meta.env.VITE_ENABLE_MOCK !== 'true') {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)

export default http
