import http from './http'

export async function loginApi(payload) {
  if (import.meta.env.VITE_ENABLE_MOCK === 'true') {
    return {
      token: 'mock-token',
      user: {
        id: 1,
        name: payload.username || '舆情分析员',
        role: '前端演示账号'
      }
    }
  }
  return http.post('/auth/login', payload)
}

export async function getUserInfoApi() {
  if (import.meta.env.VITE_ENABLE_MOCK === 'true') {
    return {
      id: 1,
      name: localStorage.getItem('opinion_user_name') || '舆情分析员',
      role: '系统管理员'
    }
  }
  return http.get('/auth/me')
}
