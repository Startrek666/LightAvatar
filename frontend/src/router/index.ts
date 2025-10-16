import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import ChatView from '@/views/ChatView.vue'

const routes: RouteRecordRaw[] = [
    {
        path: '/',
        name: 'Chat',
        component: ChatView
    },
    {
        path: '/settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue')
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router
