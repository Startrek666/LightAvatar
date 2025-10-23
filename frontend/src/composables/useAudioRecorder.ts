import { ref } from 'vue'

export function useAudioRecorder() {
    const isRecording = ref(false)
    const mediaRecorder = ref<MediaRecorder | null>(null)
    const audioChunks = ref<Blob[]>([])
    const stream = ref<MediaStream | null>(null)

    const startRecording = async (onDataAvailable?: (data: ArrayBuffer) => void) => {
        try {
            // Request microphone access
            stream.value = await navigator.mediaDevices.getUserMedia({ audio: true })

            // Create MediaRecorder
            mediaRecorder.value = new MediaRecorder(stream.value, {
                mimeType: 'audio/webm'
            })

            // Handle data available
            mediaRecorder.value.ondataavailable = async (event) => {
                if (event.data.size > 0) {
                    audioChunks.value.push(event.data)

                    if (onDataAvailable) {
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
            // 立即清除回调，防止stop()后触发的ondataavailable继续发送数据
            mediaRecorder.value.ondataavailable = null
            
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
