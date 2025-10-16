import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
    const sessionId = ref('')
    const isConnected = ref(false)
    const messages = ref<Array<{
        role: 'user' | 'assistant'
        content: string
        timestamp: Date
    }>>([])

    const settings = ref({
        llm: {
            api_url: 'http://localhost:8080/v1',
            api_key: '',
            model: 'qwen-plus'
        },
        tts: {
            voice: 'zh-CN-XiaoxiaoNeural'
        },
        avatar: {
            template: 'default.mp4'
        }
    })

    const addMessage = (message: { role: 'user' | 'assistant', content: string }) => {
        messages.value.push({
            ...message,
            timestamp: new Date()
        })
    }

    const clearMessages = () => {
        messages.value = []
    }

    const updateSettings = (newSettings: any) => {
        settings.value = { ...settings.value, ...newSettings }
    }

    return {
        sessionId,
        isConnected,
        messages,
        settings,
        addMessage,
        clearMessages,
        updateSettings
    }
})
