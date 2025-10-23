<template>
  <div class="profile-container">
    <div class="profile-header">
      <div class="header-content">
        <h1 class="header-title">个人中心</h1>
        <a-space :size="12">
          <a-button @click="$router.push('/chat')" v-if="userInfo?.can_use_avatar" size="large">
            返回对话
          </a-button>
          <a-button @click="handleLogout" danger size="large">退出登录</a-button>
        </a-space>
      </div>
    </div>

    <div class="profile-content">
      <a-row :gutter="[24, 24]">
        <!-- 用户信息卡片 -->
        <a-col :xs="24" :lg="12">
          <a-card class="info-card" :bordered="false">
            <div class="card-header">
              <div class="avatar-section">
                <a-avatar :size="72" style="background: linear-gradient(135deg, #C9A961 0%, #A67C00 100%)">
                  {{ userInfo?.username?.charAt(0).toUpperCase() }}
                </a-avatar>
                <div class="user-title">
                  <h2>{{ userInfo?.username }}</h2>
                  <p>{{ userInfo?.email }}</p>
                </div>
              </div>
            </div>

            <a-divider style="margin: 20px 0" />

            <div class="info-items">
              <div class="info-item">
                <span class="info-label">角色</span>
                <a-tag :color="userInfo?.role === 'admin' ? '#C9A961' : '#666'" class="info-value-tag">
                  {{ userInfo?.role === 'admin' ? '管理员' : '普通用户' }}
                </a-tag>
              </div>

              <div class="info-item">
                <span class="info-label">数字人权限</span>
                <a-tag :color="userInfo?.can_use_avatar ? '#52C41A' : '#D9D9D9'" class="info-value-tag">
                  {{ userInfo?.can_use_avatar ? '已开通' : '未开通' }}
                </a-tag>
              </div>

              <div class="info-item">
                <span class="info-label">账户状态</span>
                <a-tag :color="userInfo?.is_active ? '#52C41A' : '#FF4D4F'" class="info-value-tag">
                  {{ userInfo?.is_active ? '正常' : '已禁用' }}
                </a-tag>
              </div>

              <div class="info-item">
                <span class="info-label">注册时间</span>
                <span class="info-value">{{ formatDate(userInfo?.created_at) }}</span>
              </div>
            </div>

            <a-alert
              v-if="!userInfo?.can_use_avatar"
              message="权限提示"
              description="您暂无数字人使用权限，如需使用请联系管理员开通"
              type="warning"
              show-icon
              style="margin-top: 20px;"
            />
          </a-card>
        </a-col>

        <!-- 修改密码卡片 -->
        <a-col :xs="24" :lg="12">
          <a-card class="password-card" :bordered="false">
            <h3 class="card-title">修改密码</h3>
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
                  size="large"
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
                  placeholder="请输入新密码（至少6位）"
                  size="large"
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
                  size="large"
                />
              </a-form-item>

              <a-form-item style="margin-bottom: 0">
                <a-button
                  type="primary"
                  html-type="submit"
                  :loading="loading"
                  size="large"
                  block
                >
                  修改密码
                </a-button>
              </a-form-item>
            </a-form>
          </a-card>
        </a-col>
      </a-row>
    </div>
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
  background: #F8F6F2;
}

.profile-header {
  background: #FFFFFF;
  border-bottom: 2px solid #C9A961;
  box-shadow: 0 4px 12px rgba(201, 169, 97, 0.08);
  padding: 24px 48px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1400px;
  margin: 0 auto;
}

.header-title {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  color: #2C2C2C;
  letter-spacing: 0.5px;
}

.profile-content {
  padding: 48px;
  max-width: 1400px;
  margin: 0 auto;
}

/* 卡片样式 */
.info-card,
.password-card {
  border-radius: 16px;
  border: 1px solid #E8D5B5;
  box-shadow: 0 8px 24px rgba(201, 169, 97, 0.12);
  overflow: hidden;
  height: 100%;
}

.info-card :deep(.ant-card-body),
.password-card :deep(.ant-card-body) {
  padding: 32px;
}

/* 用户头像区域 */
.card-header {
  margin-bottom: 8px;
}

.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.avatar-section :deep(.ant-avatar) {
  font-size: 32px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-title h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #2C2C2C;
  line-height: 1.3;
}

.user-title p {
  margin: 4px 0 0;
  font-size: 14px;
  color: #666;
}

/* 信息列表 */
.info-items {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: #FDFBF7;
  border-radius: 8px;
  border: 1px solid #F5EBD4;
}

.info-label {
  font-size: 15px;
  font-weight: 500;
  color: #666;
}

.info-value {
  font-size: 15px;
  color: #2C2C2C;
  font-weight: 500;
}

.info-value-tag {
  font-size: 14px;
  padding: 4px 12px;
  border-radius: 6px;
  border: none;
  font-weight: 500;
}

/* 修改密码卡片 */
.card-title {
  margin: 0 0 24px;
  font-size: 20px;
  font-weight: 600;
  color: #2C2C2C;
}

/* 表单样式 */
.profile-content :deep(.ant-form-item-label > label) {
  font-size: 15px;
  font-weight: 500;
  color: #2C2C2C;
}

.profile-content :deep(.ant-input),
.profile-content :deep(.ant-input-password),
.profile-content :deep(.ant-input-affix-wrapper) {
  border-radius: 8px;
  border-color: #E0E0E0;
  font-size: 15px;
}

.profile-content :deep(.ant-input:hover),
.profile-content :deep(.ant-input-password:hover),
.profile-content :deep(.ant-input-affix-wrapper:hover) {
  border-color: #C9A961;
}

.profile-content :deep(.ant-input:focus),
.profile-content :deep(.ant-input-password:focus),
.profile-content :deep(.ant-input-affix-wrapper-focused) {
  border-color: #C9A961;
  box-shadow: 0 0 0 2px rgba(201, 169, 97, 0.1);
}

.profile-content :deep(.ant-btn-primary) {
  height: 48px;
  font-size: 16px;
  font-weight: 500;
  background: linear-gradient(135deg, #C9A961 0%, #A67C00 100%);
  border: none;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(201, 169, 97, 0.3);
}

.profile-content :deep(.ant-btn-primary:hover) {
  background: linear-gradient(135deg, #D4B76E 0%, #B88A00 100%);
  box-shadow: 0 6px 16px rgba(201, 169, 97, 0.4);
  transform: translateY(-1px);
}

.profile-content :deep(.ant-btn-primary:active) {
  transform: translateY(0);
}

.profile-content :deep(.ant-btn-dangerous) {
  border-radius: 8px;
}

.profile-content :deep(.ant-alert-warning) {
  background: #FFF9ED;
  border: 1px solid #F5D8A1;
  border-radius: 8px;
}

.profile-content :deep(.ant-divider) {
  border-color: #F5EBD4;
}

/* 响应式设计 */
@media (max-width: 992px) {
  .profile-content {
    padding: 24px;
  }

  .info-card,
  .password-card {
    margin-bottom: 24px;
  }
}

@media (max-width: 768px) {
  .profile-header {
    padding: 16px 20px;
  }

  .header-title {
    font-size: 20px;
  }

  .header-content {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }

  .header-content :deep(.ant-space) {
    width: 100%;
  }

  .header-content :deep(.ant-btn) {
    flex: 1;
  }

  .profile-content {
    padding: 16px;
  }

  .info-card :deep(.ant-card-body),
  .password-card :deep(.ant-card-body) {
    padding: 20px;
  }

  .avatar-section {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .user-title h2 {
    font-size: 20px;
  }

  .info-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .card-title {
    font-size: 18px;
  }
}
</style>
