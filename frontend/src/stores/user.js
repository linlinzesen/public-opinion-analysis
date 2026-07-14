import { reactive } from 'vue'

export const userStore = reactive({
  user: JSON.parse(localStorage.getItem('opinion_user') || 'null'),
  setUser(user) {
    this.user = user
    localStorage.setItem('opinion_user', JSON.stringify(user))
    localStorage.setItem('opinion_user_name', user?.name || '')
  },
  logout() {
    this.user = null
    localStorage.removeItem('opinion_token')
    localStorage.removeItem('opinion_user')
    localStorage.removeItem('opinion_user_name')
  }
})
