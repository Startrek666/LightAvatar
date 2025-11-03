<template>
  <a-modal
    v-model:open="internalVisible"
    :title="null"
    :footer="null"
    :closable="true"
    :maskClosable="false"
    :keyboard="true"
    width="800px"
    class="search-progress-modal"
    @cancel="handleClose"
  >
    <div class="search-progress-container">
      <!-- 头部 -->
      <div class="progress-header">
        <div class="header-title">
          <span class="title-icon">🔍</span>
          <span class="title-text">多Agent搜索进行中</span>
        </div>
        <div class="header-actions">
          <span v-if="autoCloseCountdown > 0" class="countdown-text">
            {{ autoCloseCountdown }}秒后自动关闭
          </span>
          <button class="close-button" @click="handleClose">
            <span>×</span>
          </button>
        </div>
      </div>

      <!-- 搜索查询 -->
      <div class="search-query">
        <div class="query-icon">🔎</div>
        <div class="query-text">{{ searchQuery }}</div>
      </div>

      <!-- 进度步骤列表 -->
      <div class="progress-steps">
        <div
          v-for="(step, index) in steps"
          :key="index"
          class="progress-step"
          :class="{
            'step-completed': step.status === 'completed',
            'step-active': step.status === 'active',
            'step-pending': step.status === 'pending'
          }"
        >
          <!-- 左侧时间线 -->
          <div class="step-timeline">
            <div class="timeline-line" v-if="index < steps.length - 1"></div>
            <div class="timeline-dot">
              <div v-if="step.status === 'completed'" class="check-icon">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path
                    d="M13.5 4.5L6 12L2.5 8.5"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    class="check-path"
                  />
                </svg>
              </div>
              <div v-else-if="step.status === 'active'" class="loading-spinner"></div>
              <div v-else class="pending-dot"></div>
            </div>
          </div>

          <!-- 步骤内容 -->
          <div class="step-content">
            <div class="step-title">{{ step.title }}</div>
            <div v-if="step.subtitle" class="step-subtitle">{{ step.subtitle }}</div>
          </div>
        </div>
      </div>

      <!-- 底部结果统计 -->
      <div v-if="searchCompleted && resultCount > 0" class="progress-footer">
        <div class="result-summary">
          <span class="result-icon">✅</span>
          <span class="result-text">搜索完成，获得 {{ resultCount }} 个结果</span>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface Step {
  title: string
  subtitle?: string
  status: 'pending' | 'active' | 'completed'
}

const props = defineProps<{
  visible: boolean
  searchQuery: string
  searchMode?: 'agent' | 'pipeline'
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

// 内部visible状态
const internalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

// 步骤定义
const steps = ref<Step[]>([
  { title: '多Agent搜索工作已启动', status: 'pending' },
  { title: '提取关键词', status: 'pending' },
  { title: '初步进行中文搜索', status: 'pending' },
  { title: '初步进行英文搜索', status: 'pending' },
  { title: '扩充中文搜索', status: 'pending' },
  { title: '补充英语资料', status: 'pending' },
  { title: '正在分析信息', status: 'pending' },
  { title: '搜索完成', status: 'pending' }
])

const searchCompleted = ref(false)
const resultCount = ref(0)
const autoCloseCountdown = ref(0)
let countdownTimer: number | null = null

// 步骤映射：将后端消息映射到前端步骤
const stepMapping: Record<string, number> = {
  '多agent搜索工作已启动': 0,
  '提取搜索关键词': 1,
  '提取关键词': 1,
  '正在搜索:': 2, // 中文搜索
  '初步进行中文搜索': 2,
  '初步进行英文搜索': 3,
  '扩充中文搜索': 4,
  '扩充搜索英语资料': 5,
  '补充英语资料': 5,
  '深度爬取内容': 6,
  '深度搜集信息': 6,
  '分析相关性': 7,
  '正在分析信息': 7,
  '搜索完成': 7,
  '找到': 7
}

// 更新进度
const updateProgress = (message: string, step: number, total: number) => {
  console.log('📊 [SearchProgressModal] 更新进度:', { message, step, total })
  
  // 检测是否是搜索完成
  if (message.includes('搜索完成') || message.includes('找到') || (step >= total && total > 0)) {
    searchCompleted.value = true
    
    // 提取结果数量
    const match = message.match(/(\d+)\s*个|(\d+)\s*篇/)
    if (match) {
      resultCount.value = parseInt(match[1] || match[2])
    }
    
    // 完成所有步骤
    steps.value.forEach((s) => {
      if (s.status === 'active') {
        s.status = 'completed'
      }
    })
    
    // 标记最后一步为完成
    if (steps.value[7]) {
      steps.value[7].status = 'completed'
      if (resultCount.value > 0) {
        steps.value[7].title = `搜索完成，获得 ${resultCount.value} 个结果`
      }
    }
    
    // 启动自动关闭倒计时
    startAutoClose()
    return
  }

  // 映射消息到步骤
  let targetStepIndex = -1
  
  // 先尝试精确匹配
  for (const [key, index] of Object.entries(stepMapping)) {
    if (message.includes(key)) {
      targetStepIndex = index
      break
    }
  }
  
  // 如果没有匹配到，根据step/total估算
  if (targetStepIndex === -1 && total > 0) {
    const progress = step / total
    targetStepIndex = Math.min(Math.floor(progress * (steps.value.length - 1)), steps.value.length - 2)
  }

  // 更新步骤状态
  if (targetStepIndex >= 0 && targetStepIndex < steps.value.length) {
    // 完成之前的步骤
    for (let i = 0; i < targetStepIndex; i++) {
      if (steps.value[i].status === 'active' || steps.value[i].status === 'pending') {
        steps.value[i].status = 'completed'
      }
    }
    
    // 激活当前步骤
    if (steps.value[targetStepIndex].status === 'pending') {
      steps.value[targetStepIndex].status = 'active'
      const cleanMessage = message.replace(/^[🔍🔑📊🕷️✂️✅🤖⚙️]\s*/g, '').trim()
      if (cleanMessage && !cleanMessage.includes('搜索完成')) {
        steps.value[targetStepIndex].subtitle = cleanMessage
      }
    }
  }
}

// 开始自动关闭倒计时
const startAutoClose = () => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
  }
  
  autoCloseCountdown.value = 5
  
  countdownTimer = window.setInterval(() => {
    autoCloseCountdown.value--
    
    if (autoCloseCountdown.value <= 0) {
      handleClose()
    }
  }, 1000)
}

// 关闭弹窗
const handleClose = () => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  emit('update:visible', false)
  emit('close')
}

// 重置状态
const reset = () => {
  steps.value.forEach(step => {
    step.status = 'pending'
    step.subtitle = undefined
  })
  searchCompleted.value = false
  resultCount.value = 0
  autoCloseCountdown.value = 0
  
  // 第一个步骤立即激活
  if (steps.value[0]) {
    steps.value[0].status = 'active'
  }
  
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

// 监听visible变化，重置状态
watch(() => props.visible, (newVal) => {
  if (newVal) {
    reset()
  }
})

// 暴露方法供父组件调用
defineExpose({
  updateProgress,
  reset
})
</script>

<style scoped lang="scss">
.search-progress-modal {
  :deep(.ant-modal-content) {
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  }

  :deep(.ant-modal-body) {
    padding: 0;
  }
}

.search-progress-container {
  display: flex;
  flex-direction: column;
  min-height: 500px;
  background: #ffffff;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 32px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: white;

  .header-title {
    display: flex;
    align-items: center;
    gap: 12px;

    .title-icon {
      font-size: 24px;
    }

    .title-text {
      font-size: 18px;
      font-weight: 600;
      color: #1a1a1a;
    }
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 16px;

    .countdown-text {
      font-size: 12px;
      color: #8c8c8c;
      font-weight: 400;
    }

    .close-button {
      width: 32px;
      height: 32px;
      border: none;
      background: transparent;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
      color: #8c8c8c;

      &:hover {
        background: #f5f5f5;
        color: #1a1a1a;
      }

      span {
        font-size: 24px;
        line-height: 1;
      }
    }
  }
}

.search-query {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 32px;
  background: white;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);

  .query-icon {
    font-size: 20px;
  }

  .query-text {
    font-size: 16px;
    color: #1a1a1a;
    font-weight: 500;
  }
}

.progress-steps {
  flex: 1;
  padding: 32px;
  overflow-y: auto;
  max-height: 500px;
}

.progress-step {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
  opacity: 0.5;
  transition: all 0.3s ease;

  &.step-completed {
    opacity: 1;
  }

  &.step-active {
    opacity: 1;
    animation: fadeIn 0.5s ease;
  }

  &.step-pending {
    opacity: 0.4;
  }

  .step-timeline {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 24px;
    flex-shrink: 0;

    .timeline-line {
      position: absolute;
      top: 24px;
      left: 50%;
      transform: translateX(-50%);
      width: 2px;
      height: calc(100% + 8px);
      background: #e8e8e8;
      z-index: 0;
    }

    .timeline-dot {
      position: relative;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: white;
      border: 2px solid #e8e8e8;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1;
      transition: all 0.3s ease;

      .check-icon {
        width: 16px;
        height: 16px;
        color: #52c41a;
        animation: checkmark 0.4s ease;

        .check-path {
          stroke-dasharray: 20;
          stroke-dashoffset: 20;
          animation: drawCheck 0.4s ease forwards;
        }
      }

      .loading-spinner {
        width: 12px;
        height: 12px;
        border: 2px solid #e8e8e8;
        border-top-color: #1890ff;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
      }

      .pending-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #e8e8e8;
      }
    }
  }

  &.step-completed .timeline-dot {
    border-color: #52c41a;
    background: #f6ffed;
  }

  &.step-active .timeline-dot {
    border-color: #1890ff;
    background: #e6f7ff;
  }

  .step-content {
    flex: 1;
    padding-top: 2px;

    .step-title {
      font-size: 15px;
      font-weight: 500;
      color: #1a1a1a;
      margin-bottom: 4px;
      transition: color 0.3s ease;
    }

    .step-subtitle {
      font-size: 13px;
      color: #8c8c8c;
      margin-top: 4px;
    }
  }

  &.step-completed .step-content .step-title {
    color: #52c41a;
  }

  &.step-active .step-content .step-title {
    color: #1890ff;
  }
}

.progress-footer {
  padding: 24px 32px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  background: white;

  .result-summary {
    display: flex;
    align-items: center;
    gap: 12px;
    justify-content: center;

    .result-icon {
      font-size: 20px;
    }

    .result-text {
      font-size: 15px;
      color: #52c41a;
      font-weight: 500;
    }
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes checkmark {
  0% {
    transform: scale(0);
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
  }
}

@keyframes drawCheck {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

