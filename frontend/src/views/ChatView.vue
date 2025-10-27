<template>
  <div class="chat-container">
    <a-layout>
      <a-layout-header class="header">
        <div class="header-content">
          <h1 class="header-title">Avatar Chat</h1>
          <div class="header-actions">
            <!-- 语音输入开关 -->
            <div class="header-action-item">
              <div class="switch-wrapper">
                <a-switch v-model:checked="enableVoiceInput" checked-children="开" un-checked-children="关" />
                <span class="action-label">语音输入</span>
              </div>
            </div>

            <!-- 对话记录开关 -->
            <div class="header-action-item">
              <div class="switch-wrapper">
                <a-switch v-model:checked="showChatHistory" checked-children="显" un-checked-children="隐" />
                <span class="action-label">对话记录</span>
              </div>
            </div>

            <!-- 联网搜索开关 -->
            <div class="header-action-item">
              <div class="switch-wrapper">
                <a-switch v-model:checked="enableWebSearch" checked-children="开" un-checked-children="关" />
                <span class="action-label">联网搜索</span>
              </div>
            </div>

            <!-- 服务器节点选择 -->
            <div class="header-action-item server-node-selector">
              <a-dropdown :trigger="['click']">
                <a-button type="text" size="small" class="node-button">
                  <span class="node-icon">{{ currentNode.icon }}</span>
                  <span class="node-name">
                    <span class="node-name-full">{{ currentNode.displayName }}</span>
                    <span class="node-name-short">{{ currentNode.shortName }}</span>
                    <span v-if="isAutoNode" class="auto-badge">自动</span>
                  </span>
                </a-button>
                <template #overlay>
                  <a-menu @click="handleNodeChange">
                    <a-menu-item 
                      v-for="node in availableNodes" 
                      :key="node.id"
                      :class="{ 'active-node': node.id === currentNode.id }">
                      <div class="node-menu-item">
                        <span class="node-menu-icon">{{ node.icon }}</span>
                        <div class="node-menu-info">
                          <div class="node-menu-name">{{ node.displayName }}</div>
                          <div class="node-menu-desc">{{ node.description }}</div>
                        </div>
                        <span v-if="node.id === currentNode.id" class="node-check">✓</span>
                      </div>
                    </a-menu-item>
                    <a-menu-divider />
                    <a-menu-item key="auto">
                      <div class="node-menu-item">
                        <span class="node-menu-icon">🌐</span>
                        <div class="node-menu-info">
                          <div class="node-menu-name">自动选择</div>
                          <div class="node-menu-desc">根据您的位置自动选择最优节点</div>
                        </div>
                        <span v-if="isAutoNode" class="node-check">✓</span>
                      </div>
                    </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </div>

            <a-tooltip title="个人中心">
              <a-button type="text" size="small" @click="goToProfile" :icon="h(UserOutlined)" />
            </a-tooltip>
            <a-tooltip title="设置">
              <a-button type="text" size="small" @click="showSettings" :icon="h(SettingOutlined)" />
            </a-tooltip>
            <a-badge :count="isConnected ? 0 : 1" :dot="true">
              <a-tooltip :title="isConnected ? '已连接' : '未连接'">
                <a-button type="text" size="small"
                  :icon="h(isConnected ? WifiOutlined : DisconnectOutlined)" />
              </a-tooltip>
            </a-badge>
          </div>
        </div>
      </a-layout-header>

      <a-layout-content class="content">
        <!-- 开始对话按钮 -->
        <div v-if="!isReady" class="start-dialog-overlay">
          <div class="start-dialog-content">
            <h2>Lemomate数字人助手</h2>
            <p>点击下方按钮开始对话</p>
            <a-button 
              type="primary" 
              size="large" 
              :loading="isInitializing"
              @click="startDialog">
              {{ isInitializing ? '准备中...' : '开始对话' }}
            </a-button>
          </div>
        </div>

        <div class="video-chat-area" v-show="isReady">
          <!-- Avatar Video Display -->
          <div class="avatar-container">
            <!-- 双 video 元素用于无缝切换 -->
            <video ref="avatarVideo1" :class="['avatar-video', { active: currentVideoIndex === 0 }]" autoplay muted
              loop playsinline />
            <video ref="avatarVideo2" :class="['avatar-video', { active: currentVideoIndex === 1 }]" autoplay muted
              loop playsinline />
            <!-- 只在无视频播放且正在处理时显示蒙层 -->
            <div v-if="showProcessingIndicator" class="processing-indicator">
              <a-spin size="large" tip="处理中..." />
            </div>
          </div>

          <!-- Chat Messages -->
          <div class="chat-messages" v-if="showChatHistory">
            <div class="messages-container" ref="messagesContainer">
              <div v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
                <div class="message-content">
                  <a-avatar v-if="message.role === 'user'" :icon="h(UserOutlined)" class="message-avatar" />
                  <a-avatar v-else :icon="h(RobotOutlined)" style="background-color: #1890ff" class="message-avatar" />
                  <div class="message-text">
                    <!-- 用户消息显示纯文本 -->
                    <template v-if="message.role === 'user'">
                      {{ message.content }}
                    </template>
                    <!-- AI消息使用 Markdown 渲染 -->
                    <template v-else>
                      <MarkdownRenderer :content="message.content" />
                    </template>
                  </div>
                </div>
                <div class="message-time">{{ formatTime(message.timestamp) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Input Area -->
        <div class="input-area" v-show="isReady">
          <!-- 文档信息卡片 -->
          <div v-if="uploadedDocInfo" class="doc-info-card">
            <div class="doc-info-content">
              <FileTextOutlined class="doc-icon" />
              <div class="doc-details">
                <span class="doc-name">{{ uploadedDocInfo.filename }}</span>
                <span class="doc-size">{{ uploadedDocInfo.textLength }} 字符</span>
              </div>
            </div>
            <CloseOutlined class="doc-close" @click="clearUploadedDoc" />
          </div>
          
          <a-input-group compact>
            <a-input v-model:value="inputText" placeholder="输入消息或按住录音按钮说话..." @pressEnter="sendTextMessage"
              :disabled="!isConnected || isProcessing" size="large" />
            <a-button size="large" @click="triggerFileUpload"
              :disabled="!isConnected || isProcessing || isUploadingDoc || !!uploadedDocInfo" :icon="h(PlusOutlined)"
              title="上传文档 (PDF/DOCX/PPTX, 最大30MB)">
            </a-button>
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
          <!-- 隐藏的文件上传输入框 -->
          <input ref="fileInput" type="file" accept=".pdf,.docx,.pptx" style="display: none" @change="handleFileUpload" />
        </div>
      </a-layout-content>
    </a-layout>

    <!-- Search Progress Modal -->
    <a-modal 
      v-model:open="searchProgressVisible" 
      title="联网搜索中" 
      :footer="null"
      :closable="false"
      :maskClosable="false"
      width="400px">
      <div class="search-progress-content">
        <a-progress 
          :percent="Math.round((searchProgress.step / searchProgress.total) * 100)" 
          status="active" 
        />
        <div class="search-progress-message">
          <a-spin :spinning="true" />
          <span style="margin-left: 12px;">{{ searchProgress.message }}</span>
        </div>
      </div>
    </a-modal>

    <!-- Settings Modal -->
    <a-modal v-model:open="settingsVisible" title="设置" width="600px" @ok="saveSettings">
      <a-form :model="settings" layout="vertical">
        <a-form-item label="LLM 大模型">
          <a-select v-model:value="settings.llm.model">
            <a-select-option value="qwen">Qwen 2.5B（通用对话）</a-select-option>
            <a-select-option value="gemma">Gemma 3B（更智能）</a-select-option>
          </a-select>
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
import { ref, h, onMounted, onUnmounted, nextTick, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  SettingOutlined,
  WifiOutlined,
  DisconnectOutlined,
  UserOutlined,
  RobotOutlined,
  SendOutlined,
  AudioOutlined,
  PlusOutlined,
  FileTextOutlined,
  CloseOutlined
} from '@ant-design/icons-vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useAudioRecorder } from '@/composables/useAudioRecorder'
import { useDocParser } from '@/composables/useDocParser'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import { 
  SERVER_NODES, 
  getCurrentNode, 
  saveSelectedNode, 
  clearSelectedNode,
  type ServerNode 
} from '@/config/server.config'
// import { useChatStore } from '@/store/chat' // 暂未使用，保留以备将来功能扩展

// const chatStore = useChatStore()
const router = useRouter()
const { connect, disconnect, send, isConnected, shouldReconnect } = useWebSocket()
const { startRecording: startAudioRecording, stopRecording: stopAudioRecording, isRecording } = useAudioRecorder()
const { parseDocument, isUploading: isUploadingDoc } = useDocParser()

// Refs
const avatarVideo1 = ref<HTMLVideoElement>()
const avatarVideo2 = ref<HTMLVideoElement>()
const currentVideoIndex = ref(0)  // 0: video1, 1: video2
const messagesContainer = ref<HTMLElement>()
const inputText = ref('')
const isProcessing = ref(false)
const fileInput = ref<HTMLInputElement>()
const uploadedDocText = ref('')
const uploadedDocInfo = ref<{ filename: string; textLength: number } | null>(null)
const isPlayingIdleVideo = ref(false)
const settingsVisible = ref(false)
const videoPlaybackUnlocked = ref(false) // 视频播放权限是否已解锁
const isReady = ref(false) // 是否已准备就绪
const isInitializing = ref(false) // 是否正在初始化

// Feature toggles
const enableVoiceInput = ref(true)  // 语音输入开关
const showChatHistory = ref(true)   // 对话记录显示开关
const enableWebSearch = ref(false)  // 联网搜索开关

// Server node selection
const availableNodes = ref<ServerNode[]>(SERVER_NODES)
const currentNode = ref<ServerNode>(getCurrentNode())
const isAutoNode = computed(() => !localStorage.getItem('selected_server_node'))

// Search progress modal
const searchProgressVisible = ref(false)
const searchProgress = ref({
  step: 0,
  total: 4,
  message: ''
})

// Video playback queue for streaming
const videoQueue = ref<Blob[]>([])
const isPlayingSpeechVideo = ref(false)
const configLoaded = ref(false)
const idleVideoUrl = ref('')

// 计算属性：只在真正等待且无视频时显示"处理中"
const showProcessingIndicator = computed(() => {
  return isProcessing.value && !isPlayingSpeechVideo.value && !isPlayingIdleVideo.value
})

// Data
const messages = ref<Array<{
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}>>([])

const settings = ref({
  llm: {
    model: 'qwen'
  },
  tts: {
    voice: 'zh-CN-XiaoxiaoNeural'
  },
  avatar: {
    template: 'default.mp4'
  }
})

// Methods
const goToProfile = () => {
  router.push('/profile')
}

const showSettings = () => {
  settingsVisible.value = true
}

// 处理节点切换
const handleNodeChange = ({ key }: { key: string }) => {
  if (key === 'auto') {
    // 清除手动选择，使用自动检测
    clearSelectedNode()
    currentNode.value = getCurrentNode()
    message.success(`已切换到自动选择节点: ${currentNode.value.displayName}`)
  } else {
    // 手动选择节点
    const selectedNode = availableNodes.value.find(node => node.id === key)
    if (selectedNode) {
      saveSelectedNode(key)
      currentNode.value = selectedNode
      message.success(`已切换到 ${selectedNode.displayName}`)
    }
  }
  
  // 显示重新连接提示
  if (isConnected.value) {
    message.info('节点已切换，请刷新页面以应用新节点', 3)
    // 可选：自动刷新页面
    setTimeout(() => {
      window.location.reload()
    }, 2000)
  }
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

// 文件上传相关函数
const triggerFileUpload = () => {
  if (fileInput.value) {
    fileInput.value.click()
  }
}

const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  
  if (!file) return

  console.log('📎 选择文件:', file.name, '类型:', file.type, '大小:', (file.size / 1024 / 1024).toFixed(2), 'MB')

  // 验证文件类型
  const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']
  if (!validTypes.includes(file.type)) {
    message.error('仅支持 PDF、DOCX、PPTX 格式的文件')
    target.value = ''
    return
  }

  // 验证文件大小（30MB）
  const maxSize = 30 * 1024 * 1024
  if (file.size > maxSize) {
    message.error('文件大小不能超过 30MB')
    target.value = ''
    return
  }

  try {
    // 调用 docparser API 解析文档
    const docText = await parseDocument(file)
    
    console.log('✅ 文档解析成功，文本长度:', docText.length)
    
    // 保存文档文本和信息
    uploadedDocText.value = docText
    uploadedDocInfo.value = {
      filename: file.name,
      textLength: docText.length
    }
    
    // 提示用户
    message.success(`文档已上传，请输入您的问题`)
    
    // 在输入框显示提示
    if (!inputText.value) {
      inputText.value = '请根据上传的文档回答问题：'
    }
  } catch (error: any) {
    message.error(error.message || '文档解析失败，请重试')
  } finally {
    // 清空文件输入，允许重复上传同一文件
    target.value = ''
  }
}

// 清除已上传的文档
const clearUploadedDoc = () => {
  uploadedDocText.value = ''
  uploadedDocInfo.value = null
  message.info('已取消文档')
}

const sendTextMessage = () => {
  console.log('📤 [sendTextMessage] 开始发送消息')
  console.log('  - inputText:', inputText.value)
  console.log('  - isConnected:', isConnected.value)
  console.log('  - isProcessing:', isProcessing.value)
  
  if (!inputText.value.trim() || !isConnected.value || isProcessing.value) {
    console.warn('⚠️ [sendTextMessage] 发送被阻止:', {
      isEmpty: !inputText.value.trim(),
      notConnected: !isConnected.value,
      isProcessing: isProcessing.value
    })
    return
  }

  // 移动端：在用户点击发送时解锁视频播放权限
  if (!videoPlaybackUnlocked.value) {
    unlockVideoPlayback()
  }

  const userInput = inputText.value.trim()
  let messageToSend = userInput
  
  // 如果有上传的文档，将文档内容添加到发送的消息中
  if (uploadedDocText.value) {
    messageToSend = `${userInput}\n\n[文档内容]\n${uploadedDocText.value}`
    console.log('📄 发送消息包含文档内容，总长度:', messageToSend.length)
    // 清空文档文本和信息，避免重复发送
    uploadedDocText.value = ''
    uploadedDocInfo.value = null
  }
  
  // Clear input immediately (multiple approaches for reliability)
  inputText.value = ''
  
  // Add user message - 只显示用户输入的提示词，不显示文档内容
  messages.value.push({
    role: 'user',
    content: userInput,
    timestamp: new Date()
  })

  // Prepare assistant message for streaming
  const assistantMessage = {
    role: 'assistant' as const,
    content: '',
    timestamp: new Date()
  }
  messages.value.push(assistantMessage)

  // Send to server with streaming enabled - 发送完整消息（包含文档）
  isProcessing.value = true
  const payload = {
    type: 'text',
    text: messageToSend,
    streaming: true,  // Enable streaming mode
    use_search: enableWebSearch.value  // 是否启用联网搜索
  }
  console.log('🚀 [sendTextMessage] 发送数据到服务器:', payload)
  send(payload)
  console.log('✅ [sendTextMessage] 消息已发送')

  // Ensure input is cleared in next tick
  nextTick(() => {
    inputText.value = ''
  })

  scrollToBottom()
}

const startRecording = async () => {
  if (isRecording.value || !isConnected.value || isProcessing.value) {
    return
  }

  // 移动端：在用户点击录音时解锁视频播放权限
  if (!videoPlaybackUnlocked.value) {
    unlockVideoPlayback()
  }

  console.log('开始录音...')
  message.info('开始录音，请说话...', 1)

  try {
    let chunkCount = 0
    await startAudioRecording((audioData: ArrayBuffer) => {
      chunkCount++
      console.log(`发送音频数据块 #${chunkCount}，大小: ${audioData.byteLength} 字节`)
      
      // Send audio data through WebSocket
      send({
        type: 'audio',
        data: Array.from(new Uint8Array(audioData))
      })
    })
    console.log('✅ 录音器启动成功')
  } catch (error) {
    console.error('❌ 录音启动失败:', error)
    message.error('无法访问麦克风')
  }
}

const stopRecording = () => {
  if (isRecording.value) {
    console.log('🛑 停止录音，发送结束信号')
    stopAudioRecording()
    
    // 发送录音结束信号
    send({
      type: 'audio_end'
    })
    
    message.loading('正在识别语音...', 0)
    isProcessing.value = true
    console.log('⏳ 等待语音识别结果...')
  } else {
    console.log('⚠️ 尝试停止录音但当前未在录音状态')
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

// 解锁视频播放权限（移动端必需）
const unlockVideoPlayback = () => {
  if (videoPlaybackUnlocked.value) return
  videoPlaybackUnlocked.value = true
}

// 使用 Web Audio API 播放短暂的静音片段，以解锁浏览器的音频/视频播放权限
const ensureMediaUnlocked = async (): Promise<boolean> => {
  const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
  if (!AudioContextClass) {
    console.warn('当前浏览器不支持 AudioContext，跳过解锁逻辑')
    videoPlaybackUnlocked.value = true
    return true
  }

  try {
    // 1. 解锁 AudioContext
    const audioContext = new AudioContextClass()
    if (audioContext.state === 'suspended') {
      await audioContext.resume()
    }

    const durationSeconds = 0.2
    const sampleRate = audioContext.sampleRate
    const frameCount = Math.max(1, Math.floor(sampleRate * durationSeconds))

    const buffer = audioContext.createBuffer(1, frameCount, sampleRate)
    const source = audioContext.createBufferSource()
    source.buffer = buffer
    source.connect(audioContext.destination)

    const playbackPromise = new Promise<void>((resolve) => {
      source.onended = () => resolve()
    })

    source.start()
    await playbackPromise

    source.disconnect()
    await audioContext.close()
    
    // 标记为已解锁，后续会在待机视频播放时进一步解锁
    videoPlaybackUnlocked.value = true
    console.log('✅ 音频权限已解锁')
    return true
  } catch (error) {
    console.warn('解锁媒体播放失败:', error)
    message.warning('浏览器阻止了媒体播放，请再次点击"开始对话"按钮')
    return false
  }
}

// WebSocket message handler
const handleWebSocketMessage = (data: any) => {
  console.log('📨 [handleWebSocketMessage] 收到消息:', data)
  
  if (data.type === 'heartbeat') {
    // Respond to heartbeat to keep connection alive
    console.log('💓 [handleWebSocketMessage] 心跳消息')
    send({ type: 'pong' })
    return
  }
  else if (data.type === 'response') {
    // Non-streaming mode (legacy)
    console.log('✅ 收到响应:', data.data.text)
    messages.value.push({
      role: 'assistant',
      content: data.data.text,
      timestamp: new Date()
    })

    message.destroy()  // 关闭loading提示
    isProcessing.value = false
    scrollToBottom()
  }
  else if (data.type === 'search_progress') {
    // Search progress update
    console.log('🔍 [handleWebSocketMessage] 搜索进度:', data.data)
    searchProgress.value = {
      step: data.data.step,
      total: data.data.total,
      message: data.data.message
    }
    
    // 显示搜索进度对话框
    if (data.data.step > 0 && data.data.step < data.data.total) {
      searchProgressVisible.value = true
    } else if (data.data.step >= data.data.total) {
      // 搜索完成，关闭对话框
      setTimeout(() => {
        searchProgressVisible.value = false
      }, 500)
    }
  }
  else if (data.type === 'text_chunk') {
    // Streaming text chunk
    console.log('📝 [handleWebSocketMessage] 收到文本块:', data.data.chunk)
    const lastMessage = messages.value[messages.value.length - 1]
    console.log('  - messages.length:', messages.value.length)
    console.log('  - lastMessage:', lastMessage)
    if (lastMessage && lastMessage.role === 'assistant') {
      lastMessage.content += data.data.chunk
      console.log('  - 已追加到assistant消息, 当前长度:', lastMessage.content.length)
      scrollToBottom()
    } else {
      console.warn('⚠️ [handleWebSocketMessage] 没有找到assistant消息或最后一条不是assistant')
    }
  }
  else if (data.type === 'session_timeout') {
    console.log('⏰ 会话超时:', data)
    const timeoutSeconds = data.timeout_seconds || 300
    message.warning(`会话已超过 ${timeoutSeconds} 秒无操作，请刷新页面或重新进入继续对话`, 0)
    // Stop auto-reconnect
    shouldReconnect.value = false
    disconnect()
  }
  else if (data.type === 'video_chunk_meta') {
    // Video chunk metadata received, binary data will follow
    console.log('🎥 视频块元数据:', data.data.size, '字节')
  }
  else if (data.type === 'stream_complete') {
    // Streaming complete
    console.log('✅ [handleWebSocketMessage] 流式传输完成:', data.data.full_text)
    console.log('  - 最终文本长度:', data.data.full_text?.length || 0)
    message.destroy()  // 关闭loading提示
    isProcessing.value = false
    console.log('  - isProcessing 设置为 false')
  }
  else if (data.type === 'error') {
    // Error occurred
    console.error('❌ [handleWebSocketMessage] 处理失败:', data.data.message)
    message.destroy()  // 关闭loading提示
    message.error('处理失败: ' + data.data.message)
    isProcessing.value = false
  }
  else {
    console.warn('⚠️ [handleWebSocketMessage] 未知消息类型:', data.type, data)
  }
}

// Handle binary video data
const handleWebSocketBinary = (videoBlob: Blob) => {
  // Add to video queue
  videoQueue.value.push(videoBlob)

  // Start playing if not already playing
  if (!isPlayingSpeechVideo.value) {
    playNextVideo()
  }
}

// Play next video in queue
const playNextVideo = async () => {
  if (videoQueue.value.length === 0) {
    isPlayingSpeechVideo.value = false
    // 播放完所有视频后，回到待机视频
    playIdleVideo()
    return
  }

  isPlayingSpeechVideo.value = true
  const videoBlob = videoQueue.value.shift()

  // 获取当前和下一个video元素
  const currentVideo = currentVideoIndex.value === 0 ? avatarVideo1.value : avatarVideo2.value
  const nextVideo = currentVideoIndex.value === 0 ? avatarVideo2.value : avatarVideo1.value

  if (videoBlob && nextVideo) {
    const url = URL.createObjectURL(videoBlob)
    
    // 预加载下一个视频
    nextVideo.src = url
    nextVideo.loop = false
    nextVideo.muted = false
    
    // 等待加载并播放
    try {
      await new Promise((resolve, reject) => {
        nextVideo.onloadeddata = async () => {
          try {
            await nextVideo.play()
            resolve(null)
          } catch (playError: any) {
            // 移动端自动播放被阻止，尝试静音播放
            if (playError.name === 'NotAllowedError') {
              console.warn('⚠️ 自动播放被阻止，尝试静音播放')
              nextVideo.muted = true
              try {
                await nextVideo.play()
                resolve(null)
              } catch (mutedError) {
                reject(mutedError)
              }
            } else {
              reject(playError)
            }
          }
        }
        nextVideo.onerror = reject
        nextVideo.load()
        
        // 超时保护
        setTimeout(() => reject(new Error('Video load timeout')), 10000)
      })
      
      // 等待一帧，确保视频已渲染
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
      
      // 切换显示的video（无缝切换）
      currentVideoIndex.value = currentVideoIndex.value === 0 ? 1 : 0

      // 停止并清理旧video
      if (currentVideo) {
        currentVideo.pause()
        if (
          currentVideo.src &&
          currentVideo.src.startsWith('blob:') &&
          currentVideo.src !== idleVideoUrl.value
        ) {
          URL.revokeObjectURL(currentVideo.src)
        }
      }

      // 切换到语音视频时，标记待机状态为false
      isPlayingIdleVideo.value = false

      // When video ends, play next
      nextVideo.onended = () => {
        URL.revokeObjectURL(url)
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

// 播放待机视频（使用双video无缝切换）
const playIdleVideo = async () => {
  if (!idleVideoUrl.value) {
    console.warn('Idle video URL not available')
    return
  }
  
  // 获取当前和下一个video元素
  const currentVideo = currentVideoIndex.value === 0 ? avatarVideo1.value : avatarVideo2.value
  const nextVideo = currentVideoIndex.value === 0 ? avatarVideo2.value : avatarVideo1.value
  
  if (!nextVideo) {
    console.error('Video element not ready')
    return
  }
  
  try {
    // 设置下一个video为待机视频
    nextVideo.src = idleVideoUrl.value
    nextVideo.loop = true
    nextVideo.muted = true
    nextVideo.autoplay = true
    
    console.log('Loading idle video:', idleVideoUrl.value)
    
    // 等待视频加载并开始播放
    await new Promise((resolve, reject) => {
      nextVideo.onloadeddata = async () => {
        try {
          await nextVideo.play()
          resolve(null)
        } catch (playError) {
          // 待机视频是静音的，如果还是失败就记录错误
          console.error('待机视频播放失败:', playError)
          reject(playError)
        }
      }
      nextVideo.onerror = reject
      nextVideo.load()
      
      // 超时保护
      setTimeout(() => reject(new Error('Video load timeout')), 10000)
    })
    
    // 等待一帧，确保视频已渲染
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    
    // 切换显示（无缝过渡）
    currentVideoIndex.value = currentVideoIndex.value === 0 ? 1 : 0
    
    // 停止并清理旧video（如果是语音视频）
    if (currentVideo && currentVideo.src && currentVideo.src !== idleVideoUrl.value) {
      currentVideo.pause()
      if (currentVideo.src.startsWith('blob:')) {
        URL.revokeObjectURL(currentVideo.src)
      }
      currentVideo.src = ''
    }
    
    isPlayingIdleVideo.value = true
    console.log('Idle video playing successfully')
  } catch (err) {
    console.error('Failed to play idle video:', err)
    console.error('Video error:', nextVideo.error)
    
    // 清理blob URL
    if (idleVideoUrl.value && idleVideoUrl.value.startsWith('blob:')) {
      URL.revokeObjectURL(idleVideoUrl.value)
      idleVideoUrl.value = ''
    }
  }
}

// 下载待机视频
const downloadIdleVideo = async () => {
  try {
    console.log('Downloading idle video...')
    const response = await fetch('/api/idle-video')
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    const blob = await response.blob()
    console.log('Downloaded blob:', blob.size, 'bytes, type:', blob.type)
    
    // 验证blob类型
    if (!blob.type.startsWith('video/')) {
      console.warn('Unexpected blob type:', blob.type)
    }
    
    idleVideoUrl.value = URL.createObjectURL(blob)
    console.log('Idle video blob URL created:', idleVideoUrl.value)
    
    // 等待下一帧确保video元素已挂载
    await nextTick()
    
    // 在用户点击后立即解锁video播放权限（关键！）
    // 先尝试以非静音模式播放待机视频一小段时间
    const videoToUnlock = avatarVideo1.value
    if (videoToUnlock && videoPlaybackUnlocked.value) {
      try {
        console.log('🔓 尝试解锁video播放权限...')
        videoToUnlock.src = idleVideoUrl.value
        videoToUnlock.muted = false  // 非静音
        videoToUnlock.volume = 1.0
        videoToUnlock.loop = true
        
        await videoToUnlock.play()
        
        // 播放500ms后再暂停，确保浏览器记录了用户手势
        await new Promise(resolve => setTimeout(resolve, 500))
        
        videoToUnlock.pause()
        videoToUnlock.currentTime = 0
        videoToUnlock.muted = true
        
        console.log('✅ Video播放权限已解锁')
      } catch (err) {
        console.warn('⚠️ Video解锁失败:', err)
      }
    }
    
    // 播放待机视频（静音模式）
    await playIdleVideo()
  } catch (error) {
    console.error('Failed to download idle video:', error)
  }
}

// 开始对话 - 初始化所有资源
const startDialog = async () => {
  if (isInitializing.value || isReady.value) return
  
  isInitializing.value = true
  
  try {
    console.log('🚀 开始初始化...')
    
    // 1. 解锁音视频播放权限（移动端关键）
    console.log('🔓 解锁音视频播放权限...')
    const unlocked = await ensureMediaUnlocked()
    if (!unlocked) {
      return
    }
    videoPlaybackUnlocked.value = true
    
    // 2. 等待video元素挂载完成
    await nextTick()
    console.log('Video elements ready:', {
      video1: !!avatarVideo1.value,
      video2: !!avatarVideo2.value
    })
    
    // 3. 下载待机视频
    console.log('🎬 下载待机视频...')
    await downloadIdleVideo()
    
    // 4. 加载配置
    console.log('⚙️ 加载配置...')
    try {
      const response = await fetch('/api/config')
      if (response.ok) {
        const config = await response.json()
        settings.value = config
        localStorage.setItem('avatar-chat-settings', JSON.stringify(config))
        configLoaded.value = true
      } else {
        const savedSettings = localStorage.getItem('avatar-chat-settings')
        if (savedSettings) {
          settings.value = JSON.parse(savedSettings)
          configLoaded.value = true
        }
      }
    } catch (error) {
      console.error('Failed to load settings:', error)
      const savedSettings = localStorage.getItem('avatar-chat-settings')
      if (savedSettings) {
        settings.value = JSON.parse(savedSettings)
        configLoaded.value = true
      }
    }
    
    // 5. 连接 WebSocket
    console.log('🔌 连接 WebSocket...')
    const sessionId = Date.now().toString()
    
    // WebSocket close handler to handle rejection due to multiple sessions
    const handleWebSocketClose = (event: CloseEvent) => {
      if (event.code === 1008) {
        // Connection rejected due to policy violation (multiple sessions)
        message.error({
          content: event.reason || '您已有一个正在使用的会话，请先退出当前会话再重试',
          duration: 5
        })
        isReady.value = false
      }
    }
    
    connect(`/ws/${sessionId}`, handleWebSocketMessage, handleWebSocketBinary, handleWebSocketClose)
    
    // 6. 等待一下让连接建立
    await new Promise(resolve => setTimeout(resolve, 500))
    
    console.log('✅ 初始化完成')
    isReady.value = true
    
  } catch (error) {
    console.error('❌ 初始化失败:', error)
    message.error('初始化失败，请刷新页面重试')
  } finally {
    isInitializing.value = false
  }
}

// Lifecycle
onMounted(async () => {
  // 只做基本准备，其他初始化由 startDialog 处理
  console.log('📦 组件已挂载，等待用户点击开始对话')
})

// Watch for WebSocket connection and send config when ready
watch(isConnected, (connected: boolean) => {
  if (connected && configLoaded.value) {
    // Send config to backend when connection is established
    send({
      type: 'config',
      config: settings.value
    })
    console.log('Configuration sent to backend')
  }
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.chat-container {
  width: 100%;
  min-height: 100vh;
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
  gap: 16px;
}

.header h1 {
  margin: 0;
  font-size: 20px;
  color: #333;
}

.header-actions {
  display: flex;
  gap: 12px;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: flex-end;
}

.header-action-item {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.switch-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

/* 服务器节点选择器样式 */
.server-node-selector .node-button {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 4px;
  transition: all 0.3s;
}

.server-node-selector .node-button:hover {
  background-color: rgba(24, 144, 255, 0.1);
}

.server-node-selector .node-icon {
  font-size: 16px;
  line-height: 1;
}

.server-node-selector .node-name {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 默认显示完整名称，隐藏短名称 */
.server-node-selector .node-name-full {
  display: inline;
}

.server-node-selector .node-name-short {
  display: none;
}

/* 移动端：隐藏完整名称，显示短名称 */
@media (max-width: 768px) {
  .server-node-selector .node-name-full {
    display: none;
  }
  
  .server-node-selector .node-name-short {
    display: inline;
  }
}

.server-node-selector .auto-badge {
  font-size: 10px;
  padding: 1px 4px;
  background-color: #52c41a;
  color: white;
  border-radius: 2px;
  font-weight: normal;
}

.node-menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
  min-width: 280px;
}

.node-menu-item .node-menu-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.node-menu-item .node-menu-info {
  flex: 1;
}

.node-menu-item .node-menu-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  line-height: 1.4;
}

.node-menu-item .node-menu-desc {
  font-size: 12px;
  color: #999;
  line-height: 1.4;
  margin-top: 2px;
}

.node-menu-item .node-check {
  color: #1890ff;
  font-size: 16px;
  font-weight: bold;
  flex-shrink: 0;
}

.active-node {
  background-color: rgba(24, 144, 255, 0.05);
}

.action-label {
  font-size: 12px;
  color: #999;
  line-height: 1;
  text-align: center;
}

.content {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
  padding: 0;
  overflow: hidden;
  position: relative;
}

/* 开始对话覆盖层 */
.start-dialog-overlay {
  position: absolute;
  inset: 0;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.start-dialog-content {
  text-align: center;
  color: #333;
  padding: 48px;
  background: #f0f2f5;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.start-dialog-content h2 {
  font-size: 32px;
  margin: 0 0 16px 0;
  font-weight: 600;
}

.start-dialog-content p {
  font-size: 16px;
  margin: 0 0 32px 0;
  opacity: 0.9;
}

.start-dialog-content .ant-btn {
  height: 48px;
  padding: 0 48px;
  font-size: 16px;
  border-radius: 24px;
  border: none;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.video-chat-area {
  flex: 1;
  display: flex;
  gap: 16px;
  padding: 16px;
  overflow: hidden;
  align-items: stretch;
  min-height: 0;
}

/* Avatar video container */
.avatar-container {
  flex: 0 0 40%;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  transition: flex 0.3s ease;
}

/* When chat history is hidden, expand avatar container */
.video-chat-area:has(.chat-messages) .avatar-container {
  flex: 0 0 40%;
}

.video-chat-area:not(:has(.chat-messages)) .avatar-container {
  flex: 1;
}

.avatar-video {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background-color: #fff;
  opacity: 0;
  z-index: 1;
  pointer-events: none;
  transition: none;
}

.avatar-video.active {
  opacity: 1;
  z-index: 2;
  pointer-events: auto;
}

.processing-indicator {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
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
  padding-bottom: 16px;
}

.message {
  margin-bottom: 16px;
}

.message-content {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
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
  flex: 0 0 auto;
  background: #fff;
  padding: 16px;
  border-top: 1px solid #f0f0f0;
}

/* 文档信息卡片样式 */
.doc-info-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #e6f7ff;
  border: 1px solid #91d5ff;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 12px;
  transition: all 0.3s;
}

.doc-info-card:hover {
  background: #d4edff;
  border-color: #69c0ff;
}

.doc-info-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.doc-icon {
  font-size: 24px;
  color: #1890ff;
  flex-shrink: 0;
}

.doc-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

.doc-name {
  font-size: 14px;
  font-weight: 500;
  color: #262626;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-size {
  font-size: 12px;
  color: #8c8c8c;
}

.doc-close {
  font-size: 16px;
  color: #8c8c8c;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.3s;
  flex-shrink: 0;
}

.doc-close:hover {
  color: #ff4d4f;
  background: rgba(255, 77, 79, 0.1);
}

.input-area .ant-input-group.ant-input-group-compact {
  display: flex;
  width: 100%;
  gap: 8px;
  align-items: stretch;
}

.input-area .ant-input-group.ant-input-group-compact > .ant-input {
  flex: 1 1 auto;
}

.input-area .ant-input-group.ant-input-group-compact > .ant-btn {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.input-area .ant-input-group.ant-input-group-compact > .ant-btn + .ant-btn {
  margin-left: 8px;
}

@media (max-width: 1024px) {
  .video-chat-area {
    flex-direction: column;
  }

  .avatar-container {
    flex: 0 0 auto;
    width: 100%;
    aspect-ratio: 3 / 4;
  }

  .chat-messages {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .header {
    padding: 0 12px;
    height: auto;
    min-height: 64px;
  }

  .header-content {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    height: auto;
    gap: 8px;
    padding: 8px 0;
  }

  .header-title {
    font-size: 16px;
    margin: 0;
    flex-shrink: 0;
  }

  .header-actions {
    width: auto;
    justify-content: flex-end;
    gap: 8px;
    flex-shrink: 0;
    display: flex;
    align-items: flex-start;
  }

  .header-action-item {
    display: flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
  }

  .switch-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }

  .action-label {
    font-size: 11px;
    color: #999;
    display: block;
  }

  .video-chat-area {
    padding: 12px;
    gap: 12px;
  }

  .chat-messages {
    padding: 12px;
  }

  .message-text {
    max-width: 100%;
  }
}

@media (max-width: 576px) {
  .header {
    padding: 0 8px;
    min-height: 56px;
  }

  .header-content {
    padding: 6px 0;
  }

  .header-title {
    font-size: 14px;
  }

  .header-actions {
    gap: 4px;
  }

  .switch-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
  }

  .action-label {
    font-size: 9px;
    color: #999;
    display: block;
    white-space: nowrap;
  }
  
  /* 超小屏幕隐藏部分标签文字 */
  .header-action-item:nth-child(2) .action-label,
  .header-action-item:nth-child(3) .action-label {
    display: none;
  }

  .avatar-display {
    aspect-ratio: 9 / 16;
  }

  .chat-messages {
    border-radius: 6px;
  }

  .input-area {
    padding: 12px;
  }

  .input-area .ant-input-group.ant-input-group-compact {
    flex-direction: column;
    gap: 8px;
  }

  .input-area .ant-input-group.ant-input-group-compact > .ant-btn + .ant-btn {
    margin-left: 0;
  }

  .input-area .ant-input-group.ant-input-group-compact > .ant-btn,
  .input-area .ant-input-group.ant-input-group-compact > .ant-input {
    width: 100%;
  }

  .messages-container {
    max-height: 40vh;
    padding-bottom: 24px;
  }

  .message-avatar {
    width: 32px;
    height: 32px;
  }

  /* 修复个人界面滑动问题 */
  .chat-messages {
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }
}

/* 搜索进度对话框样式 */
.search-progress-content {
  padding: 16px 0;
}

.search-progress-message {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 16px;
  font-size: 14px;
  color: #666;
}
</style>
