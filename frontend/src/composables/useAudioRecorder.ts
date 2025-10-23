import { ref } from 'vue'

export function useAudioRecorder() {
    const isRecording = ref(false)
    const mediaRecorder = ref<MediaRecorder | null>(null)
    const audioChunks = ref<Blob[]>([])
    const stream = ref<MediaStream | null>(null)
    const shouldSendData = ref(true)  // 控制是否发送数据

    const startRecording = async (onDataAvailable?: (data: ArrayBuffer) => void) => {
        try {
            // Request microphone access
            stream.value = await navigator.mediaDevices.getUserMedia({ audio: true })

            // Create MediaRecorder
            mediaRecorder.value = new MediaRecorder(stream.value, {
                mimeType: 'audio/webm'
            })

            // 重置发送标志
            shouldSendData.value = true

            // Handle data available
            mediaRecorder.value.ondataavailable = async (event) => {
                if (event.data.size > 0) {
                    audioChunks.value.push(event.data)

                    // 只有当shouldSendData为true时才发送数据
                    if (shouldSendData.value && onDataAvailable) {
                        // Convert to ArrayBuffer for sending
                        const arrayBuffer = await event.data.arrayBuffer()
                        onDataAvailable(arrayBuffer)
                    }
                }
            }

            // Start recording
            mediaRecorder.value.start(100) // Send data every 100ms
            isRecording.value = true

        } catch (error) {
            console.error('Failed to start recording:', error)
            throw error
        }
    }

    const stopRecording = () => {
        if (mediaRecorder.value && isRecording.value) {
            // 立即禁用数据发送，防止stop()后触发的ondataavailable继续发送数据
            shouldSendData.value = false
            console.log('🛑 禁用数据发送')
            
            mediaRecorder.value.stop()
            isRecording.value = false

            // Stop all tracks
            if (stream.value) {
                stream.value.getTracks().forEach(track => track.stop())
                stream.value = null
            }

            // Clear chunks
            audioChunks.value = []
            
            console.log('🛑 录音器已完全停止')
        }
    }

    const getAudioBlob = () => {
        return new Blob(audioChunks.value, { type: 'audio/webm' })
    }

    return {
        isRecording,
        startRecording,
        stopRecording,
        getAudioBlob
    }
}
