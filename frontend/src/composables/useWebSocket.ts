import { ref, onUnmounted } from 'vue'
import { getWebSocketUrl } from '../config/server.config'

export function useWebSocket() {
    const ws = ref<WebSocket | null>(null)
    const isConnected = ref(false)
    const shouldReconnect = ref(true)
    const messageHandler = ref<((data: any) => void) | null>(null)
    const binaryHandler = ref<((data: Blob) => void) | null>(null)
    const closeHandler = ref<((event: CloseEvent) => void) | null>(null)

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

        ws.value.onclose = (event: CloseEvent) => {
            console.log('WebSocket disconnected')
            isConnected.value = false

            // Call close handler if provided
            if (closeHandler.value) {
                closeHandler.value(event)
            }

            // Check if close was due to user already having an active session
            // Code 1008 is used for policy violations
            if (event.code === 1008) {
                console.warn('Connection rejected:', event.reason)
                // Don't attempt to reconnect if rejected due to multiple sessions
                shouldReconnect.value = false
                return
            }

            // Attempt to reconnect after 3 seconds if allowed
            if (shouldReconnect.value) {
                setTimeout(() => {
                    if (!isConnected.value && shouldReconnect.value) {
                        connect(url, messageHandler.value || undefined, binaryHandler.value || undefined, closeHandler.value || undefined)
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
