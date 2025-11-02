import { ref, onUnmounted } from 'vue'
import { getWebSocketUrl } from '../config/server.config'
import { isTokenInvalidReason, redirectToLogin } from '../utils/auth'
import i18n from '../i18n'

export function useWebSocket() {
    const ws = ref<WebSocket | null>(null)
    const isConnected = ref(false)
    const shouldReconnect = ref(true)
    const isReconnecting = ref(false)  // 是否正在重连
    const messageHandler = ref<((data: any) => void) | null>(null)
    const binaryHandler = ref<((data: Blob) => void) | null>(null)
    const closeHandler = ref<((event: CloseEvent) => void) | null>(null)
    const onConnectionChange = ref<((connected: boolean, isReconnecting: boolean) => void) | null>(null)

    const connect = (url: string, onMessage?: (data: any) => void, onBinary?: (data: Blob) => void, onClose?: (event: CloseEvent) => void) => {
        if (ws.value?.readyState === WebSocket.OPEN) {
            return
        }

        // Reset reconnect flag when manually connecting
        shouldReconnect.value = true

        // Build WebSocket URL with token using selected server node
        const token = localStorage.getItem('auth_token')
        const wsUrl = token 
            ? `${getWebSocketUrl(url)}?token=${encodeURIComponent(token)}`
            : getWebSocketUrl(url)

        console.log('Connecting to WebSocket:', wsUrl)
        ws.value = new WebSocket(wsUrl)
        ws.value.binaryType = 'blob'  // Set binary type to blob for video

        if (onMessage) {
            messageHandler.value = onMessage
        }

        if (onBinary) {
            binaryHandler.value = onBinary
        }

        if (onClose) {
            closeHandler.value = onClose
        }

        ws.value.onopen = () => {
            console.log('WebSocket connected')
            const wasReconnecting = isReconnecting.value
            isConnected.value = true
            isReconnecting.value = false
            // 通知连接状态变化
            if (onConnectionChange.value) {
                onConnectionChange.value(true, wasReconnecting)
            }
        }

        ws.value.onmessage = (event) => {
            // Handle binary data (video chunks)
            if (event.data instanceof Blob) {
                if (binaryHandler.value) {
                    binaryHandler.value(event.data)
                }
                return
            }

            // Handle JSON data
            try {
                const data = JSON.parse(event.data)
                if (messageHandler.value) {
                    messageHandler.value(data)
                }
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error)
            }
        }

        ws.value.onerror = (error) => {
            console.error('WebSocket error:', error)
        }

        ws.value.onclose = (event: CloseEvent) => {
            console.log('WebSocket disconnected')
            const wasConnected = isConnected.value
            isConnected.value = false

            // Call close handler if provided
            if (closeHandler.value) {
                closeHandler.value(event)
            }

            // Check if close was due to user already having an active session
            // Code 1008 is used for policy violations
            if (event.code === 1008) {
                console.warn('Connection rejected:', event.reason)
                
                // 检查是否是token无效导致的拒绝
                if (isTokenInvalidReason(event.reason || '')) {
                    // Token无效，清理本地存储并跳转登录页
                    console.warn(i18n.global.t('auth.tokenInvalid'))
                    redirectToLogin()
                }
                
                // Don't attempt to reconnect if rejected due to multiple sessions or invalid token
                shouldReconnect.value = false
                isReconnecting.value = false
                // 通知连接状态变化
                if (onConnectionChange.value && wasConnected) {
                    onConnectionChange.value(false, false)
                }
                return
            }

            // Attempt to reconnect after 3 seconds if allowed
            if (shouldReconnect.value && wasConnected) {
                isReconnecting.value = true
                // 通知连接断开，正在重连
                if (onConnectionChange.value) {
                    onConnectionChange.value(false, true)
                }
                
                setTimeout(() => {
                    if (!isConnected.value && shouldReconnect.value) {
                        connect(url, messageHandler.value || undefined, binaryHandler.value || undefined, closeHandler.value || undefined)
                    }
                }, 3000)
            } else if (onConnectionChange.value && wasConnected) {
                // 如果不重连，也通知连接断开
                onConnectionChange.value(false, false)
            }
        }
    }

    const disconnect = () => {
        if (ws.value) {
            ws.value.close()
            ws.value = null
            isConnected.value = false
        }
    }

    const send = (data: any) => {
        if (ws.value?.readyState === WebSocket.OPEN) {
            ws.value.send(JSON.stringify(data))
        } else {
            console.error('WebSocket is not connected')
        }
    }

    onUnmounted(() => {
        disconnect()
    })

    const setConnectionChangeHandler = (handler: (connected: boolean, isReconnecting: boolean) => void) => {
        onConnectionChange.value = handler
    }

    return {
        connect,
        disconnect,
        send,
        isConnected,
        isReconnecting,
        shouldReconnect,
        setConnectionChangeHandler
    }
}
