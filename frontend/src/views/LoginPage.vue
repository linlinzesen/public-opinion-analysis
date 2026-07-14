<template>
  <main class="login-page">
    <section class="login-visual">
      <div class="login-visual__content">
        <span>多源采集 · 智能识别 · 风险研判</span>
        <h1>网络舆情事件智能分析系统</h1>
        <p>面向热点事件发现、传播趋势分析、群众情感识别和分析报告生成的一体化前端演示系统。</p>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <h2>账号登录</h2>
        <p>进入舆情监测工作台</p>
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submit">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" size="large" placeholder="请输入用户名">
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input v-model="form.password" size="large" type="password" show-password placeholder="请输入密码">
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          <el-button type="primary" size="large" class="login-button" :loading="loading" @click="submit">
            登录
          </el-button>
        </el-form>
      </div>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { loginApi } from '../api/auth'
import { userStore } from '../stores/user'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: '123456'
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function submit() {
  await formRef.value?.validate()
  loading.value = true
  try {
    const result = await loginApi(form)
    localStorage.setItem('opinion_token', result.token)
    userStore.setUser(result.user)
    ElMessage.success('登录成功')
    router.push('/')
  } finally {
    loading.value = false
  }
}
</script>
