<template>
  <el-container class="app-shell">
    <el-aside width="248px" class="app-sidebar">
      <div class="brand">
        <div class="brand__mark">舆</div>
        <div>
          <strong>舆情智能分析</strong>
          <span>Opinion Insight</span>
        </div>
      </div>
      <el-menu :default-active="activeMenu" router class="side-menu">
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon>
          <span>系统首页</span>
        </el-menu-item>
        <el-menu-item index="/events">
          <el-icon><TrendCharts /></el-icon>
          <span>事件看板</span>
        </el-menu-item>
        <el-menu-item index="/crawl">
          <el-icon><Cloudy /></el-icon>
          <span>爬取控制</span>
        </el-menu-item>
        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-topbar">
        <div class="app-topbar__title">{{ route.meta.title || '网络舆情事件智能分析系统' }}</div>
        <div class="app-topbar__actions">
          <el-tag effect="plain" type="success">在线监测中</el-tag>
          <el-dropdown trigger="click" @command="handleCommand">
            <button class="user-button">
              <el-icon><UserFilled /></el-icon>
              <span>{{ userStore.user?.name || '分析员' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { userStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const activeMenu = computed(() => {
  if (route.path.startsWith('/events')) {
    return '/events'
  }
  return route.path
})

function handleCommand(command) {
  if (command === 'profile') {
    router.push('/profile')
    return
  }
  if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}
</script>
