import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../layouts/AppLayout.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginPage.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('../views/HomePage.vue'),
        meta: { title: '系统首页' }
      },
      {
        path: 'events',
        name: 'events',
        component: () => import('../views/EventBoardPage.vue'),
        meta: { title: '舆情事件看板' }
      },
      {
        path: 'events/:id',
        name: 'event-detail',
        component: () => import('../views/EventDetailPage.vue'),
        meta: { title: '事件详情' }
      },
      {
        path: 'crawl',
        name: 'crawl',
        component: () => import('../views/CrawlControlPage.vue'),
        meta: { title: '爬取控制' }
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('../views/ProfilePage.vue'),
        meta: { title: '个人中心' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('../views/NotFoundPage.vue'),
    meta: { public: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to) => {
  const token = localStorage.getItem('opinion_token')
  if (!to.meta.public && !token) {
    return '/login'
  }
  if (to.name === 'login' && token) {
    return '/'
  }
  return true
})

export default router
