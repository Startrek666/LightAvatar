<template>
  <div class="admin-container">
    <a-layout>
      <a-layout-header class="admin-header">
        <div class="header-content">
          <h1>管理后台</h1>
          <a-space>
            <span>{{ userInfo?.username }} (管理员)</span>
            <a-button @click="handleLogout">退出登录</a-button>
          </a-space>
        </div>
      </a-layout-header>

      <a-layout-content class="admin-content">
        <a-card title="用户管理" :bordered="false">
          <a-table
            :columns="columns"
            :data-source="users"
            :loading="loading"
            :pagination="{ pageSize: 10 }"
            row-key="id"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'role'">
                <a-tag :color="record.role === 'admin' ? 'red' : 'blue'">
                  {{ record.role === 'admin' ? '管理员' : '普通用户' }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'can_use_avatar'">
                <a-tag :color="record.can_use_avatar ? 'green' : 'default'">
                  {{ record.can_use_avatar ? '可使用' : '不可用' }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'is_active'">
                <a-tag :color="record.is_active ? 'success' : 'error'">
                  {{ record.is_active ? '正常' : '禁用' }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'actions'">
                <a-space>
                  <a-button
                    size="small"
                    @click="toggleAvatarPermission(record)"
                  >
                    {{ record.can_use_avatar ? '禁用数字人' : '启用数字人' }}
                  </a-button>
                  
                  <a-button
                    size="small"
                    @click="toggleUserStatus(record)"
                    :danger="record.is_active"
                  >
                    {{ record.is_active ? '禁用账号' : '启用账号' }}
                  </a-button>

                  <a-popconfirm
                    title="确定删除该用户吗？"
                    @confirm="deleteUser(record)"
                    ok-text="确定"
                    cancel-text="取消"
                  >
                    <a-button size="small" danger>删除</a-button>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>

        <a-card title="系统统计" :bordered="false" style="margin-top: 16px;">
          <a-row :gutter="16">
            <a-col :span="6">
              <a-statistic
                title="总用户数"
                :value="stats.totalUsers"
                :value-style="{ color: '#3f8600' }"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="可用数字人用户"
                :value="stats.avatarUsers"
                :value-style="{ color: '#1890ff' }"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="管理员数"
                :value="stats.adminUsers"
                :value-style="{ color: '#cf1322' }"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="活跃用户"
                :value="stats.activeUsers"
              />
            </a-col>
          </a-row>
        </a-card>
      </a-layout-content>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import axios from '@/utils/axios'

interface UserInfo {
  id: number
  username: string
  email: string
  role: string
  can_use_avatar: boolean
  created_at: string
  last_login?: string
  is_active: boolean
}

const router = useRouter()
const loading = ref(false)
const users = ref([])
const userInfo = ref<UserInfo | null>(null)

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
  { title: '用户名', dataIndex: 'username', key: 'username' },
  { title: '邮箱', dataIndex: 'email', key: 'email' },
  { title: '角色', key: 'role', width: 100 },
  { title: '数字人权限', key: 'can_use_avatar', width: 120 },
  { title: '状态', key: 'is_active', width: 80 },
  { title: '注册时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '操作', key: 'actions', width: 300 }
]

const stats = computed(() => {
  return {
    totalUsers: users.value.length,
    avatarUsers: users.value.filter((u: any) => u.can_use_avatar).length,
    adminUsers: users.value.filter((u: any) => u.role === 'admin').length,
    activeUsers: users.value.filter((u: any) => u.is_active).length
  }
})

const loadUsers = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/auth/users')
    users.value = response.data
  } catch (error: any) {
    message.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

const toggleAvatarPermission = async (user: any) => {
  try {
    await axios.put(`/api/auth/users/${user.id}/permission`, {
      can_use_avatar: !user.can_use_avatar
    })
    message.success('权限更新成功')
    await loadUsers()
  } catch (error: any) {
    message.error('权限更新失败')
  }
}

const toggleUserStatus = async (user: any) => {
  try {
    await axios.put(`/api/auth/users/${user.id}/toggle-status`)
    message.success('状态更新成功')
    await loadUsers()
  } catch (error: any) {
    message.error('状态更新失败')
  }
}

const deleteUser = async (user: any) => {
  try {
    await axios.delete(`/api/auth/users/${user.id}`)
    message.success('用户删除成功')
    await loadUsers()
  } catch (error: any) {
    message.error(error.response?.data?.detail || '删除失败')
  }
}

const handleLogout = () => {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user_info')
  message.success('已退出登录')
  router.push('/login')
}

onMounted(async () => {
  // 检查登录状态和权限
  const token = localStorage.getItem('auth_token')
  const userInfoStr = localStorage.getItem('user_info')
  
  if (!token || !userInfoStr) {
    message.error('请先登录')
    router.push('/login')
    return
  }

  userInfo.value = JSON.parse(userInfoStr)
  
  if (!userInfo.value || userInfo.value.role !== 'admin') {
    message.error('需要管理员权限')
    router.push('/chat')
    return
  }

  await loadUsers()
})
</script>

<style scoped>
.admin-container {
  min-height: 100vh;
  background: #f0f2f5;
}

.admin-header {
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

.admin-content {
  padding: 24px;
  min-height: calc(100vh - 64px);
}

@media (max-width: 768px) {
  .admin-header {
    padding: 0 16px;
  }

  .admin-content {
    padding: 16px;
  }

  .header-content h1 {
    font-size: 16px;
  }
}
</style>
