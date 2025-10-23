import { createRouter, createWebHistory, RouteRecordRaw, NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import ChatView from '@/views/ChatView.vue'
import LoginView from '@/views/LoginView.vue'
import AdminView from '@/views/AdminView.vue'
import ProfileView from '@/views/ProfileView.vue'

const routes: RouteRecordRaw[] = [
    {
        path: '/',
        redirect: '/login'
    },
    {
        path: '/login',
        name: 'Login',
        component: LoginView,
        meta: { requiresGuest: true }
    },
    {
        path: '/chat',
        name: 'Chat',
        component: ChatView,
        meta: { requiresAuth: true, requiresAvatar: true }
    },
    {
        path: '/admin',
        name: 'Admin',
        component: AdminView,
        meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
        path: '/profile',
        name: 'Profile',
        component: ProfileView,
        meta: { requiresAuth: true }
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

// 路由守卫
router.beforeEach((to: RouteLocationNormalized, _from: RouteLocationNormalized, next: NavigationGuardNext) => {
    const token = localStorage.getItem('auth_token')
    const userInfoStr = localStorage.getItem('user_info')
    const userInfo = userInfoStr ? JSON.parse(userInfoStr) : null

    // 需要访客权限（已登录用户不能访问）
    if (to.meta.requiresGuest && token) {
        if (userInfo?.role === 'admin') {
            next('/admin')
        } else if (userInfo?.can_use_avatar) {
            next('/chat')
        } else {
            next('/profile')
        }
        return
    }

    // 需要登录
    if (to.meta.requiresAuth && !token) {
        console.log('需要登录')
        next('/login')
        return
    }

    // 需要管理员权限
    if (to.meta.requiresAdmin && userInfo?.role !== 'admin') {
        console.log('需要管理员权限')
        next('/chat')
        return
    }

    // 需要数字人使用权限
    if (to.meta.requiresAvatar && !userInfo?.can_use_avatar) {
        console.log('您暂无数字人使用权限')
        next('/profile')
        return
    }

    next()
})

export default router
