<template>
  <div class="chat-container">
    <a-layout>
      <a-layout-header class="header">
        <div class="header-content">
          <h1>Lightweight Avatar Chat</h1>
          <div class="header-actions">
            <!-- 语音输入开关 -->
            <a-space>
              <span>语音输入:</span>
              <a-switch v-model:checked="enableVoiceInput" checked-children="开" un-checked-children="关" />
            </a-space>

            <!-- 对话记录开关 -->
            <a-space>
              <span>对话记录:</span>
              <a-switch v-model:checked="showChatHistory" checked-children="显示" un-checked-children="隐藏" />
            </a-space>

            <a-button @click="showSettings" :icon="h(SettingOutlined)">设置</a-button>
            <a-badge :count="isConnected ? 0 : 1" :dot="true">
              <a-button :type="isConnected ? 'primary' : 'default'"
                :icon="h(isConnected ? WifiOutlined : DisconnectOutlined)">
                {{ isConnected ? '已连接' : '未连接' }}
              </a-button>
            </a-badge>
          </div>
        </div>
      </a-layout-header>

      <a-layout-content class="content">
        <div class="video-chat-area">
          <!-- Avatar Video Display -->
          <div class="avatar-display">
            <video ref="avatarVideo" class="avatar-video" autoplay playsinline :poster="avatarPoster" />
            <div v-if="isProcessing" class="processing-indicator">
              <a-spin size="large" tip="处理中..." />
            </div>
          </div>

          <!-- Chat Messages -->
          <div class="chat-messages" v-if="showChatHistory">
            <div class="messages-container" ref="messagesContainer">
              <div v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
                <div class="message-content">
                  <a-avatar v-if="message.role === 'user'" :icon="h(UserOutlined)" />
                  <a-avatar v-else :icon="h(RobotOutlined)" style="background-color: #1890ff" />
                  <div class="message-text">{{ message.content }}</div>
                </div>
                <div class="message-time">{{ formatTime(message.timestamp) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Input Area -->
        <div class="input-area">
          <a-input-group compact>
            <a-input v-model:value="inputText" placeholder="输入消息或按住录音按钮说话..." @pressEnter="sendTextMessage"
              :disabled="!isConnected || isProcessing" size="large" />
            <a-button type="primary" size="large" @click="sendTextMessage"
              :disabled="!inputText || !isConnected || isProcessing" :icon="h(SendOutlined)">
              发送
            </a-button>
            <a-button v-if="enableVoiceInput" :type="isRecording ? 'danger' : 'default'" size="large"
              @mousedown="startRecording" @mouseup="stopRecording" @mouseleave="stopRecording"
              @touchstart="startRecording" @touchend="stopRecording" :disabled="!isConnected || isProcessing"
              :icon="h(AudioOutlined)">
              {{ isRecording ? '录音中' : '按住说话' }}
            </a-button>
          </a-input-group>
        </div>
      </a-layout-content>
    </a-layout>

    <!-- Settings Modal -->
    <a-modal v-model:open="settingsVisible" title="设置" width="600px" @ok="saveSettings">
      <a-form :model="settings" layout="vertical">
        <a-form-item label="LLM API 地址">
          <a-input v-model:value="settings.llm.api_url" placeholder="http://localhost:8080/v1" />
        </a-form-item>
        <a-form-item label="LLM API Key">
          <a-input-password v-model:value="settings.llm.api_key" placeholder="输入API Key" />
        </a-form-item>
        <a-form-item label="LLM 模型">
          <a-input v-model:value="settings.llm.model" placeholder="qwen-plus" />
        </a-form-item>
        <a-form-item label="TTS 语音">
          <a-select v-model:value="settings.tts.voice">
            <a-select-option value="zh-CN-XiaoxiaoNeural">晓晓（女）</a-select-option>
            <a-select-option value="zh-CN-YunxiNeural">云希（男）</a-select-option>
            <a-select-option value="zh-CN-YunjianNeural">云健（男）</a-select-option>
            <a-select-option value="zh-CN-XiaoyiNeural">晓伊（女）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="数字人模板">
          <a-select v-model:value="settings.avatar.template">
            <a-select-option value="default.mp4">默认</a-select-option>
            <a-select-option value="female.mp4">女性形象</a-select-option>
            <a-select-option value="male.mp4">男性形象</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted, onUnmounted, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import {
  SettingOutlined,
  WifiOutlined,
  DisconnectOutlined,
  UserOutlined,
  RobotOutlined,
  SendOutlined,
  AudioOutlined
} from '@ant-design/icons-vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useAudioRecorder } from '@/composables/useAudioRecorder'
// import { useChatStore } from '@/store/chat' // 暂未使用，保留以备将来功能扩展

// const chatStore = useChatStore()
const { connect, disconnect, send, isConnected } = useWebSocket()
const { startRecording: startAudioRecording, stopRecording: stopAudioRecording, isRecording } = useAudioRecorder()

// Refs
const avatarVideo = ref<HTMLVideoElement>()
const messagesContainer = ref<HTMLElement>()
const inputText = ref('')
const isProcessing = ref(false)
const settingsVisible = ref(false)
const avatarPoster = ref('data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="512" height="512"%3E%3Crect fill="%23333" width="512" height="512"/%3E%3Ctext fill="%23fff" font-size="24" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle"%3EAvatar%3C/text%3E%3C/svg%3E')

// Feature toggles
const enableVoiceInput = ref(true)  // 语音输入开关
const showChatHistory = ref(true)   // 对话记录显示开关

// Video playback queue for streaming
const videoQueue = ref<Blob[]>([])
const isPlayingVideo = ref(false)

// Data
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

// Methods
const showSettings = () => {
  settingsVisible.value = true
}

const saveSettings = async () => {
  try {
    const response = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings.value)
    })

    if (response.ok) {
      message.success('设置已保存')
      settingsVisible.value = false

      // Send config update through WebSocket
      if (isConnected.value) {
        send({
          type: 'config',
          config: settings.value
        })
      }
    } else {
      message.error('保存设置失败')
    }
  } catch (error) {
    message.error('保存设置出错')
  }
}

const sendTextMessage = () => {
  if (!inputText.value.trim() || !isConnected.value || isProcessing.value) {
    return
  }

  const messageText = inputText.value.trim()
  inputText.value = ''

  // Add user message
  messages.value.push({
    role: 'user',
    content: messageText,
    timestamp: new Date()
  })

  // Prepare assistant message for streaming
  const assistantMessage = {
    role: 'assistant' as const,
    content: '',
    timestamp: new Date()
  }
  messages.value.push(assistantMessage)

  // Send to server with streaming enabled
  isProcessing.value = true
  send({
    type: 'text',
    text: messageText,
    streaming: true  // Enable streaming mode
  })

  scrollToBottom()
}

const startRecording = async () => {
  if (!isConnected.value || isProcessing.value) {
    return
  }

  try {
    await startAudioRecording((audioData: ArrayBuffer) => {
      // Send audio data through WebSocket
      send({
        type: 'audio',
        data: Array.from(new Uint8Array(audioData))
      })
    })
  } catch (error) {
    message.error('无法访问麦克风')
  }
}

const stopRecording = () => {
  if (isRecording.value) {
    stopAudioRecording()
    isProcessing.value = true
  }
}

const formatTime = (date: Date) => {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(date)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// WebSocket message handler
const handleWebSocketMessage = (data: any) => {
  if (data.type === 'heartbeat') {
    // Respond to heartbeat to keep connection alive
    send({ type: 'pong' })
    return
  }
  else if (data.type === 'response') {
    // Non-streaming mode (legacy)
    messages.value.push({
      role: 'assistant',
      content: data.data.text,
      timestamp: new Date()
    })

    isProcessing.value = false
    scrollToBottom()
  }
  else if (data.type === 'text_chunk') {
    // Streaming text chunk
    const lastMessage = messages.value[messages.value.length - 1]
    if (lastMessage && lastMessage.role === 'assistant') {
      lastMessage.content += data.data.chunk
      scrollToBottom()
    }
  }
  else if (data.type === 'video_chunk_meta') {
    // Video chunk metadata received, binary data will follow
    console.log('Video chunk incoming:', data.data.size, 'bytes')
  }
  else if (data.type === 'stream_complete') {
    // Streaming complete
    isProcessing.value = false
    console.log('Stream complete, full text:', data.data.full_text)
  }
  else if (data.type === 'error') {
    // Error occurred
    message.error('处理失败: ' + data.data.message)
    isProcessing.value = false
  }
}

// Handle binary video data
const handleWebSocketBinary = (videoBlob: Blob) => {
  // Add to video queue
  videoQueue.value.push(videoBlob)

  // Start playing if not already playing
  if (!isPlayingVideo.value) {
    playNextVideo()
  }
}

// Play next video in queue
const playNextVideo = async () => {
  if (videoQueue.value.length === 0) {
    isPlayingVideo.value = false
    return
  }

  isPlayingVideo.value = true
  const videoBlob = videoQueue.value.shift()

  if (videoBlob && avatarVideo.value) {
    const url = URL.createObjectURL(videoBlob)
    avatarVideo.value.src = url

    try {
      await avatarVideo.value.play()

      // When video ends, play next
      avatarVideo.value.onended = () => {
        URL.revokeObjectURL(url)  // Clean up
        playNextVideo()
      }
    } catch (error) {
      console.error('Video playback error:', error)
      URL.revokeObjectURL(url)
      playNextVideo()  // Try next video
    }
  } else {
    playNextVideo()
  }
}

// Lifecycle
onMounted(async () => {
  // Connect WebSocket with binary handler
  const sessionId = Date.now().toString()
  connect(`/ws/${sessionId}`, handleWebSocketMessage, handleWebSocketBinary)

  // Load settings from server
  try {
    const response = await fetch('/api/config')
    if (response.ok) {
      const config = await response.json()
      settings.value = config
      // Save to localStorage as backup
      localStorage.setItem('avatar-chat-settings', JSON.stringify(config))
    } else {
      // Fallback to localStorage
      const savedSettings = localStorage.getItem('avatar-chat-settings')
      if (savedSettings) {
        settings.value = JSON.parse(savedSettings)
      }
    }
  } catch (error) {
    console.error('Failed to load settings from server:', error)
    // Fallback to localStorage
    try {
      const savedSettings = localStorage.getItem('avatar-chat-settings')
      if (savedSettings) {
        settings.value = JSON.parse(savedSettings)
      }
    } catch (e) {
      console.error('Failed to load settings from localStorage:', error)
    }
  }
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.chat-container {
  width: 100%;
  height: 100vh;
  background: #f0f2f5;
}

.header {
  background: #fff;
  padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.header h1 {
  margin: 0;
  font-size: 20px;
  color: #333;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.content {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
  padding: 0;
}

.video-chat-area {
  flex: 1;
  display: flex;
  gap: 16px;
  padding: 16px;
  overflow: hidden;
}

.avatar-display {
  flex: 0 0 40%;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: flex 0.3s ease;
}

/* When chat history is hidden, expand avatar display */
.video-chat-area:has(.chat-messages:not([style*="display: none"])) .avatar-display {
  flex: 0 0 40%;
}

.video-chat-area:not(:has(.chat-messages)) .avatar-display,
.video-chat-area .avatar-display:only-child {
  flex: 1;
}

.avatar-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.processing-indicator {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-messages {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}

.message {
  margin-bottom: 16px;
}

.message-content {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message.user .message-content {
  flex-direction: row-reverse;
}

.message-text {
  background: #f0f2f5;
  padding: 8px 12px;
  border-radius: 8px;
  max-width: 70%;
  word-wrap: break-word;
}

.message.user .message-text {
  background: #1890ff;
  color: #fff;
}

.message-time {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
  text-align: right;
}

.message.user .message-time {
  text-align: right;
  margin-right: 48px;
}

.message.assistant .message-time {
  text-align: left;
  margin-left: 48px;
}

.input-area {
  background: #fff;
  padding: 16px;
  border-top: 1px solid #f0f0f0;
}

@media (max-width: 768px) {
  .video-chat-area {
    flex-direction: column;
  }

  .avatar-display {
    flex: 0 0 300px;
  }
}
</style>
