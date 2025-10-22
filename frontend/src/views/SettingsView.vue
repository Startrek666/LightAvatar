<template>
  <div class="settings-container">
    <a-page-header
      title="系统设置"
      @back="() => $router.push('/')"
    />
    
    <div class="settings-content">
      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="llm" tab="语言模型">
          <a-form :model="settings.llm" layout="vertical">
            <a-form-item label="选择模型">
              <a-select v-model:value="settings.llm.model">
                <a-select-option value="qwen">Qwen 2.5B（通用对话）</a-select-option>
                <a-select-option value="gemma">Gemma 3B（英文优化）</a-select-option>
              </a-select>
              <template #extra>
                选择适合您需求的大语言模型
              </template>
            </a-form-item>
            
            <a-form-item label="Temperature">
              <a-slider
                v-model:value="settings.llm.temperature"
                :min="0"
                :max="2"
                :step="0.1"
                :marks="{ 0: '0', 1: '1', 2: '2' }"
              />
            </a-form-item>
            
            <a-form-item label="最大Token数">
              <a-input-number 
                v-model:value="settings.llm.max_tokens"
                :min="50"
                :max="4000"
                :step="50"
              />
            </a-form-item>
            
            <a-form-item label="系统提示词">
              <a-textarea
                v-model:value="settings.llm.system_prompt"
                :rows="4"
              />
            </a-form-item>
          </a-form>
        </a-tab-pane>
        
        <a-tab-pane key="whisper" tab="语音识别">
          <a-form :model="settings.whisper" layout="vertical">
            <a-form-item label="Whisper 模型">
              <a-select v-model:value="settings.whisper.model">
                <a-select-option value="tiny">Tiny (39M)</a-select-option>
                <a-select-option value="base">Base (74M)</a-select-option>
                <a-select-option value="small">Small (244M)</a-select-option>
                <a-select-option value="medium">Medium (769M)</a-select-option>
                <a-select-option value="large-v2">Large-v2 (1550M)</a-select-option>
                <a-select-option value="large-v3">Large-v3 (1550M)</a-select-option>
              </a-select>
            </a-form-item>
            
            <a-form-item label="识别语言">
              <a-select v-model:value="settings.whisper.language">
                <a-select-option value="zh">中文</a-select-option>
                <a-select-option value="en">English</a-select-option>
                <a-select-option value="ja">日本語</a-select-option>
                <a-select-option value="ko">한국어</a-select-option>
              </a-select>
            </a-form-item>
          </a-form>
        </a-tab-pane>
        
        <a-tab-pane key="tts" tab="语音合成">
          <a-form :model="settings.tts" layout="vertical">
            <a-form-item label="Edge TTS 语音">
              <a-select v-model:value="settings.tts.voice">
                <a-select-opt-group label="中文女声">
                  <a-select-option value="zh-CN-XiaoxiaoNeural">晓晓</a-select-option>
                  <a-select-option value="zh-CN-XiaoyiNeural">晓伊</a-select-option>
                  <a-select-option value="zh-CN-liaoning-XiaobeiNeural">晓北(东北话)</a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="中文男声">
                  <a-select-option value="zh-CN-YunxiNeural">云希</a-select-option>
                  <a-select-option value="zh-CN-YunjianNeural">云健</a-select-option>
                  <a-select-option value="zh-CN-YunxiaNeural">云夏</a-select-option>
                </a-select-opt-group>
              </a-select>
            </a-form-item>
            
            <a-form-item label="语速">
              <a-slider
                v-model:value="settings.tts.rate"
                :min="-50"
                :max="50"
                :marks="{ '-50': '-50%', 0: '0%', 50: '+50%' }"
              />
            </a-form-item>
            
            <a-form-item label="音调">
              <a-slider
                v-model:value="settings.tts.pitch"
                :min="-50"
                :max="50"
                :marks="{ '-50': '-50Hz', 0: '0Hz', 50: '+50Hz' }"
              />
            </a-form-item>
          </a-form>
        </a-tab-pane>
        
        <a-tab-pane key="avatar" tab="数字人">
          <a-form :model="settings.avatar" layout="vertical">
            <a-form-item label="帧率">
              <a-radio-group v-model:value="settings.avatar.fps">
                <a-radio :value="20">20 FPS</a-radio>
                <a-radio :value="25">25 FPS</a-radio>
                <a-radio :value="30">30 FPS</a-radio>
              </a-radio-group>
            </a-form-item>
            
            <a-form-item label="分辨率">
              <a-select v-model:value="settings.avatar.resolution">
                <a-select-option :value="[256, 256]">256x256</a-select-option>
                <a-select-option :value="[512, 512]">512x512</a-select-option>
                <a-select-option :value="[640, 480]">640x480</a-select-option>
                <a-select-option :value="[1280, 720]">1280x720</a-select-option>
              </a-select>
            </a-form-item>
            
            <a-form-item label="数字人模板">
              <a-upload
                v-model:fileList="avatarTemplateList"
                :maxCount="1"
                accept="video/*,image/*"
                @change="handleAvatarTemplateChange"
              >
                <a-button :icon="h(UploadOutlined)">选择模板文件</a-button>
              </a-upload>
            </a-form-item>
            
            <a-form-item>
              <a-checkbox v-model:checked="settings.avatar.static_mode">
                静态模式（仅使用第一帧）
              </a-checkbox>
            </a-form-item>
            
            <a-form-item>
              <a-checkbox v-model:checked="settings.avatar.enhance_mode">
                增强模式（边缘融合）
              </a-checkbox>
            </a-form-item>
          </a-form>
        </a-tab-pane>
      </a-tabs>
      
      <div class="settings-actions">
        <a-button @click="resetSettings">恢复默认</a-button>
        <a-button type="primary" @click="saveSettings">保存设置</a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const activeTab = ref('llm')
const avatarTemplateList = ref([])

const settings = ref({
  llm: {
    api_url: 'http://localhost:8080/v1',
    api_key: '',
    model: 'qwen-plus',
    temperature: 0.7,
    max_tokens: 500,
    system_prompt: '你是一个友好的AI助手，请用简洁清晰的语言回答问题。'
  },
  whisper: {
    model: 'small',
    language: 'zh'
  },
  tts: {
    voice: 'zh-CN-XiaoxiaoNeural',
    rate: 0,
    pitch: 0
  },
  avatar: {
    fps: 25,
    resolution: [512, 512],
    template: 'default.mp4',
    static_mode: false,
    enhance_mode: false
  }
})

const handleAvatarTemplateChange = (info: any) => {
  if (info.file.status === 'done') {
    settings.value.avatar.template = info.file.name
    message.success('模板文件已选择')
  }
}

const saveSettings = async () => {
  try {
    // Save to server
    const response = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings.value)
    })
    
    if (response.ok) {
      // Save to localStorage
      localStorage.setItem('avatar-chat-settings', JSON.stringify(settings.value))
      message.success('设置已保存')
      
      // Navigate back
      router.push('/')
    } else {
      message.error('保存设置失败')
    }
  } catch (error) {
    message.error('保存设置出错')
  }
}

const resetSettings = () => {
  settings.value = {
    llm: {
      api_url: 'http://localhost:8080/v1',
      api_key: '',
      model: 'qwen-plus',
      temperature: 0.7,
      max_tokens: 500,
      system_prompt: '你是一个友好的AI助手，请用简洁清晰的语言回答问题。'
    },
    whisper: {
      model: 'small',
      language: 'zh'
    },
    tts: {
      voice: 'zh-CN-XiaoxiaoNeural',
      rate: 0,
      pitch: 0
    },
    avatar: {
      fps: 25,
      resolution: [512, 512],
      template: 'default.mp4',
      static_mode: false,
      enhance_mode: false
    }
  }
  
  message.success('已恢复默认设置')
}

onMounted(() => {
  // Load saved settings
  try {
    const savedSettings = localStorage.getItem('avatar-chat-settings')
    if (savedSettings) {
      settings.value = JSON.parse(savedSettings)
    }
  } catch (error) {
    console.error('Failed to load settings:', error)
  }
})
</script>

<style scoped>
.settings-container {
  min-height: 100vh;
  background: #f0f2f5;
}

.settings-content {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.settings-actions {
  margin-top: 24px;
  display: flex;
  justify-content: space-between;
}
</style>
