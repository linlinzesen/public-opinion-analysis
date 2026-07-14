import http from './http'
import { mockKeywordsFollowed, mockPlatformsFollowed } from './mock'

let platformRows = [...mockPlatformsFollowed]
let keywordRows = [...mockKeywordsFollowed]

const mockEnabled = () => import.meta.env.VITE_ENABLE_MOCK === 'true'

export async function getFollowPlatformsApi() {
  if (mockEnabled()) return platformRows
  const result = await http.get('/user/follow-platforms')
  return Array.isArray(result) ? result : result.records || result.data || []
}

export async function addFollowPlatformApi(payload) {
  if (mockEnabled()) {
    const row = { id: Date.now(), ...payload }
    platformRows.unshift(row)
    return row
  }
  return http.post('/user/follow-platforms', payload)
}

export async function deleteFollowPlatformApi(id) {
  if (mockEnabled()) {
    platformRows = platformRows.filter((row) => row.id !== id)
    return true
  }
  return http.delete(`/user/follow-platforms/${id}`)
}

export async function getFollowKeywordsApi() {
  if (mockEnabled()) return keywordRows
  const result = await http.get('/user/follow-keywords')
  return Array.isArray(result) ? result : result.records || result.data || []
}

export async function addFollowKeywordApi(payload) {
  if (mockEnabled()) {
    const row = { id: Date.now(), ...payload }
    keywordRows.unshift(row)
    return row
  }
  return http.post('/user/follow-keywords', payload)
}

export async function deleteFollowKeywordApi(id) {
  if (mockEnabled()) {
    keywordRows = keywordRows.filter((row) => row.id !== id)
    return true
  }
  return http.delete(`/user/follow-keywords/${id}`)
}

export async function changePasswordApi(payload) {
  return http.post('/user/change-password', payload)
}
