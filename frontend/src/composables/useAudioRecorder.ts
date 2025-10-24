import { ref } from 'vue'

export function useAudioRecorder() {
    const isRecording = ref(false)
    const stream = ref<MediaStream | null>(null)
    const shouldSendData = ref(true)  // 控制是否发送数据
    const audioContext = ref<AudioContext | null>(null)
    const processor = ref<ScriptProcessorNode | null>(null)

    const startRecording = async (onDataAvailable?: (data: ArrayBuffer) => void) => {
        try {
            // Request microphone access with specific constraints
            stream.value = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    channelCount: 1,  // 单声道
                    sampleRate: 16000,  // 16kHz
                    echoCancellation: true,
                    noiseSuppression: true
                } 
            })

            console.log('🎤 使用 AudioContext 录制 PCM 格式')
            
            // 使用 AudioContext 处理音频为 PCM 格式
            audioContext.value = new AudioContext({ sampleRate: 16000 })
            const source = audioContext.value.createMediaStreamSource(stream.value)
            
            // 创建音频处理器（4096 是缓冲区大小）
            processor.value = audioContext.value.createScriptProcessor(4096, 1, 1)

            // 重置发送标志
            shouldSendData.value = true

            // 处理音频数据
            processor.value.onaudioprocess = (e: AudioProcessingEvent) => {
                if (!shouldSendData.value) return
                
                // 获取音频数据（Float32Array）
                const inputData = e.inputBuffer.getChannelData(0)
                
                // 转换为 Int16Array (PCM 16-bit)
                const pcmData = new Int16Array(inputData.length)
                for (let i = 0; i < inputData.length; i++) {
                    // 将 -1.0 到 1.0 的浮点数转换为 -32768 到 32767 的整数
                    const s = Math.max(-1, Math.min(1, inputData[i]))
                    pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
                }
                
                // 发送 PCM 数据
                if (onDataAvailable) {
                    onDataAvailable(pcmData.buffer)
                }
            }
            
            // 连接音频节点
            source.connect(processor.value)
            processor.value.connect(audioContext.value.destination)
            
            isRecording.value = true
            console.log('✅ PCM 录音器已启动')

        } catch (error) {
            console.error('Failed to start recording:', error)
            throw error
        }
    }

    const stopRecording = () => {
        if (isRecording.value) {
            // 立即禁用数据发送
            shouldSendData.value = false
            console.log('🛑 禁用数据发送')
            
            // 断开音频节点
            if (processor.value) {
                processor.value.disconnect()
                processor.value.onaudioprocess = null
                processor.value = null
            }
            
            // 关闭 AudioContext
            if (audioContext.value) {
                audioContext.value.close()
                audioContext.value = null
            }
            
            isRecording.value = false

            // Stop all tracks
            if (stream.value) {
                stream.value.getTracks().forEach(track => track.stop())
                stream.value = null
            }
            
            console.log('🛑 PCM 录音器已完全停止')
        }
    }

    return {
        isRecording,
        startRecording,
        stopRecording
    }
}
