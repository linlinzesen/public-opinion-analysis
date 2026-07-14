<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="监测配置"
      title="个人中心"
      description="维护关注平台 URL 和关注关键词，作为舆情采集与筛选的配置来源。"
    />

    <div class="two-column">
      <ChartPanel title="修改密码" min-height="280px">
        <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef" label-width="100px" class="password-form">
          <el-form-item label="当前密码" prop="oldPassword">
            <el-input v-model="passwordForm.oldPassword" type="password" show-password placeholder="请输入当前密码" />
          </el-form-item>
          <el-form-item label="新密码" prop="newPassword">
            <el-input v-model="passwordForm.newPassword" type="password" show-password placeholder="请输入新密码（至少6位）" />
          </el-form-item>
          <el-form-item label="确认新密码" prop="confirmPassword">
            <el-input v-model="passwordForm.confirmPassword" type="password" show-password placeholder="请再次输入新密码" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Lock" :loading="changing" @click="changePassword">修改密码</el-button>
          </el-form-item>
        </el-form>
      </ChartPanel>

      <ChartPanel title="关注平台 URL 管理" min-height="420px">
        <el-form :model="platformForm" class="inline-form">
          <el-input v-model="platformForm.name" placeholder="平台名称" />
          <el-input v-model="platformForm.url" placeholder="平台 URL" />
          <el-button type="primary" :icon="Plus" @click="addPlatform">新增</el-button>
        </el-form>

        <el-table :data="platforms" stripe>
          <el-table-column prop="name" label="平台" width="120" />
          <el-table-column prop="url" label="URL" min-width="220" show-overflow-tooltip />
          <el-table-column label="操作" width="92" align="right">
            <template #default="{ row }">
              <el-button text type="danger" :icon="Delete" @click="removePlatform(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </ChartPanel>

      <ChartPanel title="关注关键词管理" min-height="420px">
        <el-form :model="keywordForm" class="inline-form">
          <el-input v-model="keywordForm.word" placeholder="关键词" />
          <el-select v-model="keywordForm.level" placeholder="关注等级">
            <el-option label="高" value="高" />
            <el-option label="中" value="中" />
            <el-option label="低" value="低" />
          </el-select>
          <el-button type="primary" :icon="Plus" @click="addKeyword">新增</el-button>
        </el-form>

        <el-table :data="keywords" stripe>
          <el-table-column prop="word" label="关键词" />
          <el-table-column prop="level" label="等级" width="100">
            <template #default="{ row }">
              <el-tag :type="row.level === '高' ? 'danger' : row.level === '中' ? 'warning' : 'success'">
                {{ row.level }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="92" align="right">
            <template #default="{ row }">
              <el-button text type="danger" :icon="Delete" @click="removeKeyword(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </ChartPanel>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Plus, Lock } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import ChartPanel from '../components/ChartPanel.vue'
import {
  addFollowKeywordApi,
  addFollowPlatformApi,
  changePasswordApi,
  deleteFollowKeywordApi,
  deleteFollowPlatformApi,
  getFollowKeywordsApi,
  getFollowPlatformsApi
} from '../api/profile'

const platforms = ref([])
const keywords = ref([])
const changing = ref(false)
const passwordFormRef = ref(null)

const platformForm = reactive({
  name: '',
  url: ''
})

const keywordForm = reactive({
  word: '',
  level: '中'
})

const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const passwordRules = {
  oldPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码长度不能少于 6 位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== passwordForm.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

async function changePassword() {
  const valid = await passwordFormRef.value?.validate().catch(() => false)
  if (!valid) return
  changing.value = true
  try {
    await changePasswordApi({
      oldPassword: passwordForm.oldPassword,
      newPassword: passwordForm.newPassword
    })
    ElMessage.success('密码修改成功')
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
    passwordFormRef.value?.resetFields()
  } catch {
    // 错误已由 http 拦截器统一提示
  } finally {
    changing.value = false
  }
}

async function loadProfile() {
  const [platformData, keywordData] = await Promise.all([
    getFollowPlatformsApi(),
    getFollowKeywordsApi()
  ])
  platforms.value = platformData
  keywords.value = keywordData
}

async function addPlatform() {
  if (!platformForm.name || !platformForm.url) {
    ElMessage.warning('请填写平台名称和 URL')
    return
  }
  await addFollowPlatformApi({ ...platformForm })
  platformForm.name = ''
  platformForm.url = ''
  await loadProfile()
}

async function removePlatform(id) {
  await deleteFollowPlatformApi(id)
  await loadProfile()
}

async function addKeyword() {
  if (!keywordForm.word) {
    ElMessage.warning('请填写关键词')
    return
  }
  await addFollowKeywordApi({ ...keywordForm })
  keywordForm.word = ''
  keywordForm.level = '中'
  await loadProfile()
}

async function removeKeyword(id) {
  await deleteFollowKeywordApi(id)
  await loadProfile()
}

onMounted(loadProfile)
</script>
