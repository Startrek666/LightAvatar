<template>
  <div class="profile-container">
    <a-layout>
      <a-layout-header class="profile-header">
        <div class="header-content">
          <h1>个人中心</h1>
          <a-space>
            <a-button @click="$router.push('/chat')" v-if="userInfo?.can_use_avatar">
              返回聊天
            </a-button>
            <a-button @click="handleLogout">退出登录</a-button>
          </a-space>
        </div>
      </a-layout-header>

      <a-layout-content class="profile-content">
        <a-card title="用户信息" :bordered="false">
          <a-descriptions :column="1" bordered>
            <a-descriptions-item label="用户名">
              {{ userInfo?.username }}
            </a-descriptions-item>
            <a-descriptions-item label="邮箱">
              {{ userInfo?.email }}
            </a-descriptions-item>
            <a-descriptions-item label="角色">
              <a-tag :color="userInfo?.role === 'admin' ? 'red' : 'blue'">
                {{ userInfo?.role === 'admin' ? '管理员' : '普通用户' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="数字人权限">
              <a-tag :color="userInfo?.can_use_avatar ? 'green' : 'default'">
                {{ userInfo?.can_use_avatar ? '已开通' : '未开通' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="账户状态">
              <a-tag :color="userInfo?.is_active ? 'success' : 'error'">
                {{ userInfo?.is_active ? '正常' : '已禁用' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="注册时间">
              {{ formatDate(userInfo?.created_at) }}
            </a-descriptions-item>
          </a-descriptions>

          <a-alert
            v-if="!userInfo?.can_use_avatar"
            message="提示"
            description="您暂无数字人使用权限，如需使用请联系管理员开通"
            type="warning"
            show-icon
            style="margin-top: 16px;"
          />
        </a-card>

        <a-card title="修改密码" :bordered="false" style="margin-top: 16px;">
          <a-form
            :model="passwordForm"
            @finish="handleChangePassword"
            layout="vertical"
          >
            <a-form-item
              label="当前密码"
              name="old_password"
              :rules="[{ required: true, message: '请输入当前密码' }]"
            >
              <a-input-password
                v-model:value="passwordForm.old_password"
                placeholder="请输入当前密码"
              />
            </a-form-item>

            <a-form-item
              label="新密码"
              name="new_password"
              :rules="[
                { required: true, message: '请输入新密码' },
                { min: 6, message: '密码至少6个字符' }
              ]"
            >
              <a-input-password
                v-model:value="passwordForm.new_password"
                placeholder="请输入新密码"
              />
            </a-form-item>

            <a-form-item
              label="确认新密码"
              name="confirm_password"
              :rules="[
                { required: true, message: '请确认新密码' },
                { validator: validateConfirmPassword }
              ]"
            >
              <a-input-password
                v-model:value="passwordForm.confirm_password"
                placeholder="请再次输入新密码"
              />
            </a-form-item>

            <a-form-item>
              <a-button
                type="primary"
                html-type="submit"
                :loading="loading"
              >
                修改密码
              </a-button>
            </a-form-item>
          </a-form>
        </a-card>
      </a-layout-content>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import axios from '@/utils/axios'

const router = useRouter()
const loading = ref(false)
const userInfo = ref<any>(null)

const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const validateConfirmPassword = (_rule: any, value: string) => {
  if (value !== passwordForm.value.new_password) {
    return Promise.reject('两次输入的密码不一致')
  }
  return Promise.resolve()
}

const handleChangePassword = async () => {
  loading.value = true
  try {
    await axios.put('/auth/change-password', {
      old_password: passwordForm.value.old_password,
      new_password: passwordForm.value.new_password
    })
    
    message.success('密码修改成功，请重新登录')
    
    // 清除登录信息
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user_info')
    
    // 跳转到登录页
    setTimeout(() => {
      router.push('/login')
    }, 1000)
  } catch (error: any) {
    message.error(error.response?.data?.detail || '密码修改失败')
  } finally {
    loading.value = false
  }
}

const handleLogout = () => {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user_info')
  message.success('已退出登录')
  router.push('/login')
}

onMounted(() => {
  const userInfoStr = localStorage.getItem('user_info')
  if (userInfoStr) {
    userInfo.value = JSON.parse(userInfoStr)
  }
})
</script>

<style scoped>
.profile-container {
  min-height: 100vh;
  background: #f0f2f5;
}

.profile-header {
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  padding: 0 24px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.header-content h1 {
  margin: 0;
  font-size: 20px;
  color: #333;
}

.profile-content {
  padding: 24px;
  max-width: 800px;
  margin: 0 auto;
}

@media (max-width: 768px) {
  .profile-header {
    padding: 0 16px;
  }

  .profile-content {
    padding: 16px;
  }

  .header-content h1 {
    font-size: 16px;
  }
}
</style>
