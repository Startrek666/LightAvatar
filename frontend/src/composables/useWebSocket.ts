import { ref, onUnmounted } from 'vue'

export function useWebSocket() {
    const ws = ref<WebSocket | null>(null)
    const isConnected = ref(false)
    const shouldReconnect = ref(true)
    const messageHandler = ref<((data: any) => void) | null>(null)
    const binaryHandler = ref<((data: Blob) => void) | null>(null)

    const connect = (url: string, onMessage?: (data: any) => void, onBinary?: (data: Blob) => void) => {
        if (ws.value?.readyState === WebSocket.OPEN) {
            return
        }

        // Reset reconnect flag when manually connecting
        shouldReconnect.value = true

        // Build WebSocket URL with token
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const host = window.location.host
        const token = localStorage.getItem('auth_token')
        const wsUrl = token 
            ? `${protocol}//${host}${url}?token=${encodeURIComponent(token)}`
            : `${protocol}//${host}${url}`

        ws.value = new WebSocket(wsUrl)
        ws.value.binaryType = 'blob'  // Set binary type to blob for video

        if (onMessage) {
            messageHandler.value = onMessage
        }

        if (onBinary) {
            binaryHandler.value = onBinary
        }

        ws.value.onopen = () => {
            console.log('WebSocket connected')
            isConnected.value = true
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

        ws.value.onclose = () => {
            console.log('WebSocket disconnected')
            isConnected.value = false

            // Attempt to reconnect after 3 seconds if allowed
            if (shouldReconnect.value) {
                setTimeout(() => {
                    if (!isConnected.value && shouldReconnect.value) {
                        connect(url, messageHandler.value || undefined)
                    }
                }, 3000)
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

    return {
        connect,
        disconnect,
        send,
        isConnected,
        shouldReconnect
    }
}
