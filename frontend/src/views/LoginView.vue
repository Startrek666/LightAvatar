<template>
  <div class="login-container">
    <a-card class="login-card" :bordered="false">
      <div class="logo-section">
        <h1>Lemomate Avatar</h1>
        <p>数字人对话系统</p>
      </div>

      <a-tabs v-model:activeKey="activeTab" centered>
        <a-tab-pane key="login" tab="登录">
          <a-form
            :model="loginForm"
            @finish="handleLogin"
            layout="vertical"
          >
            <a-form-item
              label="用户名"
              name="username"
              :rules="[{ required: true, message: '请输入用户名' }]"
            >
              <a-input
                v-model:value="loginForm.username"
                placeholder="请输入用户名"
                size="large"
              >
                <template #prefix>
                  <UserOutlined />
                </template>
              </a-input>
            </a-form-item>

            <a-form-item
              label="密码"
              name="password"
              :rules="[{ required: true, message: '请输入密码' }]"
            >
              <a-input-password
                v-model:value="loginForm.password"
                placeholder="请输入密码"
                size="large"
              >
                <template #prefix>
                  <LockOutlined />
                </template>
              </a-input-password>
            </a-form-item>

            <a-form-item>
              <a-button
                type="primary"
                html-type="submit"
                size="large"
                block
                :loading="loading"
              >
                登录
              </a-button>
            </a-form-item>
          </a-form>
        </a-tab-pane>

        <a-tab-pane key="register" tab="注册">
          <a-form
            :model="registerForm"
            @finish="handleRegister"
            layout="vertical"
          >
            <a-form-item
              label="用户名"
              name="username"
              :rules="[
                { required: true, message: '请输入用户名' },
                { min: 3, message: '用户名至少3个字符' }
              ]"
            >
              <a-input
                v-model:value="registerForm.username"
                placeholder="请输入用户名"
                size="large"
              >
                <template #prefix>
                  <UserOutlined />
                </template>
              </a-input>
            </a-form-item>

            <a-form-item
              label="邮箱"
              name="email"
              :rules="[
                { required: true, message: '请输入邮箱' },
                { type: 'email', message: '请输入有效的邮箱地址' }
              ]"
            >
              <a-input
                v-model:value="registerForm.email"
                placeholder="请输入邮箱"
                size="large"
              >
                <template #prefix>
                  <MailOutlined />
                </template>
              </a-input>
            </a-form-item>

            <a-form-item
              label="密码"
              name="password"
              :rules="[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6个字符' }
              ]"
            >
              <a-input-password
                v-model:value="registerForm.password"
                placeholder="请输入密码"
                size="large"
              >
                <template #prefix>
                  <LockOutlined />
                </template>
              </a-input-password>
            </a-form-item>

            <a-form-item>
              <a-button
                type="primary"
                html-type="submit"
                size="large"
                block
                :loading="loading"
              >
                注册
              </a-button>
            </a-form-item>
          </a-form>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons-vue'
import axios from '@/utils/axios'

const router = useRouter()
const activeTab = ref('login')
const loading = ref(false)

const loginForm = ref({
  username: '',
  password: ''
})

const registerForm = ref({
  username: '',
  email: '',
  password: ''
})

const handleLogin = async () => {
  loading.value = true
  try {
    const response = await axios.post('/auth/login', loginForm.value)
    const { token, user } = response.data
    
    // 保存token和用户信息
    localStorage.setItem('auth_token', token)
    localStorage.setItem('user_info', JSON.stringify(user))
    
    message.success('登录成功')
    
    // 根据角色跳转
    if (user.role === 'admin') {
      router.push('/admin')
    } else {
      if (user.can_use_avatar) {
        router.push('/chat')
      } else {
        message.warning('您暂无数字人使用权限，请联系管理员')
        router.push('/profile')
      }
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  loading.value = true
  try {
    const response = await axios.post('/auth/register', registerForm.value)
    const { token, user } = response.data
    
    // 保存token和用户信息
    localStorage.setItem('auth_token', token)
    localStorage.setItem('user_info', JSON.stringify(user))
    
    message.success('注册成功')
    router.push('/profile')
  } catch (error: any) {
    message.error(error.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #F8F6F2;
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 450px;
  border-radius: 12px;
  background: #FFFFFF;
  border: 2px solid #C9A961;
  box-shadow: 0 8px 32px rgba(201, 169, 97, 0.15);
}

.login-card :deep(.ant-card-body) {
  padding: 48px 40px;
}

.logo-section {
  text-align: center;
  margin-bottom: 40px;
}

.logo-section h1 {
  font-size: 32px;
  font-weight: 600;
  color: #2C2C2C;
  margin: 0 0 8px 0;
  letter-spacing: 0.5px;
}

.logo-section p {
  font-size: 15px;
  color: #666;
  margin: 0;
  font-weight: 400;
}

.login-card :deep(.ant-tabs-nav) {
  margin-bottom: 32px;
}

.login-card :deep(.ant-tabs-tab) {
  font-size: 16px;
  font-weight: 500;
  color: #666;
}

.login-card :deep(.ant-tabs-tab-active) {
  color: #C9A961;
}

.login-card :deep(.ant-tabs-ink-bar) {
  background: #C9A961;
  height: 3px;
}

.login-card :deep(.ant-input),
.login-card :deep(.ant-input-password) {
  border-radius: 8px;
  border-color: #E0E0E0;
  font-size: 15px;
}

.login-card :deep(.ant-input:hover),
.login-card :deep(.ant-input-password:hover) {
  border-color: #C9A961;
}

.login-card :deep(.ant-input:focus),
.login-card :deep(.ant-input-password:focus),
.login-card :deep(.ant-input-affix-wrapper-focused) {
  border-color: #C9A961;
  box-shadow: 0 0 0 2px rgba(201, 169, 97, 0.1);
}

.login-card :deep(.ant-form-item-label > label) {
  font-size: 14px;
  font-weight: 500;
  color: #2C2C2C;
}

.login-card :deep(.ant-btn-primary) {
  height: 44px;
  font-size: 16px;
  font-weight: 500;
  background: linear-gradient(135deg, #C9A961 0%, #A67C00 100%);
  border: none;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(201, 169, 97, 0.3);
}

.login-card :deep(.ant-btn-primary:hover) {
  background: linear-gradient(135deg, #D4B76E 0%, #B88A00 100%);
  box-shadow: 0 6px 16px rgba(201, 169, 97, 0.4);
}

.login-card :deep(.ant-btn-primary:active) {
  background: linear-gradient(135deg, #B8985A 0%, #956F00 100%);
}

.login-card :deep(.anticon) {
  color: #C9A961;
}

@media (max-width: 576px) {
  .login-container {
    padding: 12px;
  }

  .login-card {
    max-width: 100%;
    border: 1px solid #C9A961;
  }

  .login-card :deep(.ant-card-body) {
    padding: 32px 24px;
  }

  .logo-section {
    margin-bottom: 32px;
  }

  .logo-section h1 {
    font-size: 26px;
  }

  .logo-section p {
    font-size: 14px;
  }
}
</style>
