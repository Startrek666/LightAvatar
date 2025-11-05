<template>
  <a-modal
    :open="internalVisible"
    @update:open="handleModalUpdate"
    :title="null"
    :footer="null"
    :closable="false"
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
          <span class="title-text">{{ t('search.modal.title') }}</span>
        </div>
        <div class="header-actions">
          <span v-if="autoCloseCountdown > 0" class="countdown-text">
            {{ t('search.modal.autoClose', { seconds: autoCloseCountdown }) }}
          </span>
          <button class="close-button" @click="handleClose">
            <span>×</span>
          </button>
        </div>
      </div>

      <!-- 搜索查询 -->
      <div class="search-query">
        <div class="query-text">{{ searchQuery }}</div>
      </div>

      <!-- 搜索结果网页标题列表 -->
      <div v-if="searchResults.length > 0" class="search-results">
        <div class="results-header">
          <span class="results-title">{{ t('search.modal.searchResults') }}</span>
          <span class="results-count">{{ searchResults.length }} {{ t('search.modal.resultsCount') }}</span>
        </div>
        <div class="results-list-container">
          <div class="results-list">
            <a
              v-for="(result, index) in searchResults"
              :key="index"
              :href="result.url"
              target="_blank"
              rel="noopener noreferrer"
              class="result-item"
            >
              <div class="result-number">{{ index + 1 }}</div>
              <div class="result-content">
                <div class="result-title-text">{{ result.title }}</div>
                <div class="result-domain">{{ getDomainName(result.url) }}</div>
              </div>
            </a>
          </div>
        </div>
      </div>

      <!-- 进度步骤列表 -->
      <div class="progress-steps">
        <div
          v-for="(step, index) in steps"
          v-show="step.status !== 'skipped'"
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
            <div v-if="step.result && step.status === 'completed'" class="step-result">{{ step.result }}</div>
          </div>
        </div>
      </div>

      <!-- 底部结果统计 -->
      <div v-if="searchCompleted && resultCount > 0" class="progress-footer">
        <div class="result-summary">
          <span class="result-icon">✅</span>
          <span class="result-text">{{ t('search.modal.completedWithResults', { count: resultCount }) }}</span>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()

interface Step {
  title: string
  subtitle?: string
  result?: string  // 用于显示步骤的结果内容（如理解问题的结果）
  status: 'pending' | 'active' | 'completed' | 'skipped'
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

// 步骤标题键值类型
type StepTitleKey = 'started' | 'understandingProblem' | 'extractingKeywords' | 'chineseSearch' | 'englishSearch' | 'expandChinese' | 'supplementEnglish' | 'analyzing' | 'analyzingMaterials' | 'deepThinking' | 'crawling' | 'splitting' | 'synthesizing' | 'completed'

// 获取步骤标题（响应式，会根据语言自动更新）
const getStepTitle = (stepKey: StepTitleKey): string => {
  return t(`search.modal.steps.${stepKey}`)
}

// 检测查询语言（用于动态调整步骤）
const detectedLanguage = ref<'zh' | 'en'>('zh')

// 基于原始查询文本检测语言
const detectLanguageFromText = (text: string): 'zh' | 'en' => {
  if (!text) return 'zh'
  return /[\u4e00-\u9fa5]/.test(text) ? 'zh' : 'en'
}

// 步骤定义（初始状态，会在 reset() 时更新为国际化文本）
// 深度模式会显示更多步骤，快速模式只显示基础步骤
// 注意：综合信息，生成回答应该是最后一步，放在搜索完成之前
const steps = ref<Step[]>([
  { title: getStepTitle('started'), status: 'pending' },
  { title: getStepTitle('understandingProblem'), status: 'pending' }, // 深度模式
  { title: getStepTitle('extractingKeywords'), status: 'pending' },
  { title: getStepTitle('englishSearch'), status: 'pending' }, // 先英文
  { title: getStepTitle('chineseSearch'), status: 'pending' }, // 后中文
  { title: getStepTitle('supplementEnglish'), status: 'pending' }, // 先扩充英文
  { title: getStepTitle('expandChinese'), status: 'pending' }, // 后扩充中文
  { title: getStepTitle('analyzing'), status: 'pending' },
  { title: getStepTitle('analyzingMaterials'), status: 'pending' }, // 深度模式
  { title: getStepTitle('deepThinking'), status: 'pending' }, // 深度模式
  { title: getStepTitle('crawling'), status: 'pending' }, // 深度模式
  { title: getStepTitle('splitting'), status: 'pending' }, // 深度模式
  { title: getStepTitle('completed'), status: 'pending' },
  { title: getStepTitle('synthesizing'), status: 'pending' } // 综合信息放在最后
])

const searchCompleted = ref(false)
const resultCount = ref(0)
const autoCloseCountdown = ref(0)
const searchResults = ref<Array<{ title: string; url: string }>>([])
let countdownTimer: number | null = null

// 步骤映射：将后端消息映射到前端步骤
// 注意：综合信息现在是第13步（最后一步），搜索完成是第12步
const stepMapping: Record<string, number> = {
  '多agent搜索工作已启动': 0,
  '理解问题': 1,
  '提取搜索关键词': 2,
  '提取关键词': 2,
  '正在搜索:': -1, // 动态判断（根据语言）
  '正在搜索英语资料:': 3, // 先英文
  '正在搜索中文资料:': 4, // 后中文
  '初步进行英文搜索': 3,
  '初步进行中文搜索': 4,
  '扩充搜索英语资料': 5, // 先扩充英文
  '补充英语资料': 5,
  '正在扩充英语资料': 5, // 新的标题
  '正在进一步深度搜索中文资料': 6, // 后扩充中文
  '扩充中文搜索': 6,
  '分析相关性': 7,
  '正在分析信息': 7,
  '分析资料': 8,
  '深度思考与推理': 9,
  '深度爬取内容': 10,
  '深度搜集信息': 10,
  '文档分块和二次检索': 11,
  '搜索完成': 12,
  '找到': 12,
  '综合信息': 13,
  '综合信息，生成回答': 13,
  '正在生成内容': 13
}

// 更新进度
const updateProgress = (message: string, step: number, total: number) => {
  console.log('📊 [SearchProgressModal] 更新进度:', { message, step, total })
  
  // 不再基于进度消息推断语言，统一使用原始查询文本的检测结果
  
  // 检测是否是搜索完成（搜索完成应该是倒数第二步，综合信息是最后一步）
  if (message.includes('搜索完成') || message.includes('找到')) {
    // 提取结果数量
    const match = message.match(/(\d+)\s*个|(\d+)\s*篇/)
    if (match) {
      resultCount.value = parseInt(match[1] || match[2])
    }
    
    // 标记"搜索完成"步骤（第12步）为完成
    const completedStepIndex = 12
    if (steps.value[completedStepIndex]) {
      steps.value[completedStepIndex].status = 'completed'
      if (resultCount.value > 0) {
        steps.value[completedStepIndex].title = `搜索完成，获得 ${resultCount.value} 个结果`
      }
    }
    
    // 完成所有当前激活的步骤（除了综合信息）
    for (let i = 0; i < completedStepIndex; i++) {
      if (steps.value[i] && steps.value[i].status === 'active') {
        steps.value[i].status = 'completed'
      }
    }
    
    // 激活"综合信息，生成回答"步骤（第13步，最后一步）
    const synthesizingStepIndex = 13
    if (steps.value[synthesizingStepIndex]) {
      steps.value[synthesizingStepIndex].status = 'active'
      // 当综合信息步骤激活时，启动倒计时（但不自动关闭，等待完成）
      startSynthesizingCountdown()
    }
    
    return  // 不在这里启动自动关闭，等综合信息完成后再关闭
  }
  
  // 检测是否是综合信息完成（这是最后一步）
  // 条件：消息包含"综合信息"或"正在生成内容"，或者step >= total（包括step=999的特殊情况）
  if (message.includes('综合信息') || message.includes('正在生成内容') || (step >= total && total > 0) || (step === 999 && total === 999)) {
    searchCompleted.value = true
    
    // 完成所有步骤
    steps.value.forEach((s) => {
      if (s.status === 'active') {
        s.status = 'completed'
      }
    })
    
    // 确保综合信息步骤（最后一步）被标记为完成
    const lastStepIndex = steps.value.length - 1
    if (steps.value[lastStepIndex]) {
      steps.value[lastStepIndex].status = 'completed'
    }
    
    // 注意：不启动新的倒计时，使用已启动的10秒倒计时（在综合信息步骤激活时已启动）
    return
  }

  // 映射消息到步骤
  let targetStepIndex = -1
  
  // 先尝试精确匹配
  for (const [key, index] of Object.entries(stepMapping)) {
    if (message.includes(key)) {
      if (index === -1) {
        // 动态判断：'正在搜索:' 根据 source 与已检测语言映射步骤（先英文后中文）
        if (message.includes('(keywords_en)') || message.includes('正在搜索英语资料:')) {
          targetStepIndex = 3  // 英文搜索（先）
        } else if (message.includes('(keywords_zh)') || message.includes('正在搜索中文资料:')) {
          targetStepIndex = 4  // 中文搜索（后）
        } else if (message.includes('(original)')) {
          targetStepIndex = detectedLanguage.value === 'en' ? 3 : 4
        } else {
          // 根据消息内容判断语言
          if (message.includes('英语') || message.includes('English') || message.includes('english')) {
            targetStepIndex = 3
          } else if (message.includes('中文') || message.includes('Chinese') || message.includes('chinese')) {
            targetStepIndex = 4
          } else {
            targetStepIndex = detectedLanguage.value === 'en' ? 3 : 4
          }
        }
      } else {
        targetStepIndex = index
      }
      break
    }
  }
  
  // 如果没有匹配到，根据step/total估算
  if (targetStepIndex === -1 && total > 0) {
    const progress = step / total
    targetStepIndex = Math.min(Math.floor(progress * (steps.value.length - 1)), steps.value.length - 2)
  }

  // 更新步骤状态（跳过被标记为skipped的步骤）
  if (targetStepIndex >= 0 && targetStepIndex < steps.value.length) {
    while (targetStepIndex < steps.value.length && steps.value[targetStepIndex].status === 'skipped') {
      targetStepIndex++
    }
    if (targetStepIndex >= steps.value.length) {
      return
    }
    for (let i = 0; i < targetStepIndex; i++) {
      if (steps.value[i].status === 'active' || steps.value[i].status === 'pending') {
        steps.value[i].status = 'completed'
      }
    }
    if (steps.value[targetStepIndex].status === 'pending') {
      steps.value[targetStepIndex].status = 'active'
      // 更新步骤标题以确保使用最新语言（响应语言切换）
      const stepKeys: StepTitleKey[] = ['started', 'understandingProblem', 'extractingKeywords', 'englishSearch', 'chineseSearch', 'supplementEnglish', 'expandChinese', 'analyzing', 'analyzingMaterials', 'deepThinking', 'crawling', 'splitting', 'completed', 'synthesizing']
      if (targetStepIndex < stepKeys.length) {
        steps.value[targetStepIndex].title = getStepTitle(stepKeys[targetStepIndex])
      }
      const cleanMessage = message.replace(/^[🔍🔑📊🕷️✂️✅🤖⚙️]\s*/g, '').trim()
      if (cleanMessage && !cleanMessage.includes('搜索完成') && !cleanMessage.includes('找到')) {
        // 如果消息包含换行符，提取第二行作为副标题
        const lines = cleanMessage.split('\n')
        if (lines.length > 1) {
          // 第一行更新标题，第二行作为副标题
          const mainTitle = lines[0].trim()
          const subtitle = lines.slice(1).join('\n').trim()
          if (mainTitle && targetStepIndex === 5) { // 补充英语资料步骤
            steps.value[targetStepIndex].title = mainTitle
          }
          if (subtitle) {
            steps.value[targetStepIndex].subtitle = subtitle
          }
        } else {
          steps.value[targetStepIndex].subtitle = cleanMessage
        }
      }
    }
    
    // 特殊处理：理解问题步骤，如果消息包含结果内容，保存到result字段
    if (targetStepIndex === 1 && message.includes('理解问题')) {
      // 检查消息中是否包含理解结果（格式：理解问题\n结果内容）
      const lines = message.split('\n')
      if (lines.length > 1) {
        const resultText = lines.slice(1).join('\n').trim()
        if (resultText && resultText.length > 0) {
          steps.value[targetStepIndex].result = resultText
        }
      }
    }
    
    // 当理解问题步骤完成时，保存结果
    if (targetStepIndex === 1 && steps.value[targetStepIndex].status === 'completed') {
      // 如果消息中包含理解结果（可能是单独的消息）
      if (message.length > 20 && !message.includes('理解问题') && !message.includes('提取') && !message.includes('搜索')) {
        steps.value[targetStepIndex].result = message
      }
    }
  }
}

// 开始综合信息步骤的倒计时（显示倒计时，倒计时结束后自动关闭）
const startSynthesizingCountdown = () => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
  }
  
  // 设置初始倒计时值（10秒）
  autoCloseCountdown.value = 10
  
  // 启动倒计时，倒计时到0时自动关闭弹窗
  countdownTimer = window.setInterval(() => {
    autoCloseCountdown.value--
    
    if (autoCloseCountdown.value <= 0) {
      // 倒计时到0时自动关闭弹窗
      handleClose()
    }
  }, 1000)
}

// 处理Modal更新
const handleModalUpdate = (val: boolean) => {
  internalVisible.value = val
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
  // 重置所有步骤状态（使用函数获取标题，确保响应语言变化）
  // 注意：综合信息应该是最后一步
  steps.value = [
    { title: getStepTitle('started'), status: 'pending' },
    { title: getStepTitle('understandingProblem'), status: 'pending' },
    { title: getStepTitle('extractingKeywords'), status: 'pending' },
    { title: getStepTitle('englishSearch'), status: 'pending' }, // 先英文
    { title: getStepTitle('chineseSearch'), status: 'pending' }, // 后中文
    { title: getStepTitle('supplementEnglish'), status: 'pending' }, // 先扩充英文
    { title: getStepTitle('expandChinese'), status: 'pending' }, // 后扩充中文
    { title: getStepTitle('analyzing'), status: 'pending' },
    { title: getStepTitle('analyzingMaterials'), status: 'pending' },
    { title: getStepTitle('deepThinking'), status: 'pending' },
    { title: getStepTitle('crawling'), status: 'pending' },
    { title: getStepTitle('splitting'), status: 'pending' },
    { title: getStepTitle('completed'), status: 'pending' },
    { title: getStepTitle('synthesizing'), status: 'pending' }  // 综合信息放在最后
  ]
  searchCompleted.value = false
  resultCount.value = 0
  autoCloseCountdown.value = 0
  searchResults.value = []
  
  // 使用原始查询文本检测语言
  detectedLanguage.value = detectLanguageFromText(props.searchQuery)
  // 注意：深度模式的步骤会在收到相应消息时激活，快速模式的步骤会被跳过
  // 这里暂时不预设跳过，让后端消息来控制
  
  // 第一个步骤立即激活
  if (steps.value[0]) {
    steps.value[0].status = 'active'
  }
  
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

// 当搜索词变化时，更新语言判定（不主动改动当前步骤，只用于后续映射）
watch(() => props.searchQuery, (val) => {
  detectedLanguage.value = detectLanguageFromText(val)
})

// 监听语言切换，更新步骤标题
watch(() => locale.value, () => {
  // 更新所有步骤的标题（保持状态不变）
  if (steps.value.length >= 8) {
    steps.value[0].title = getStepTitle('started')
    steps.value[1].title = getStepTitle('understandingProblem')
    steps.value[2].title = getStepTitle('extractingKeywords')
    steps.value[3].title = getStepTitle('englishSearch') // 先英文
    steps.value[4].title = getStepTitle('chineseSearch') // 后中文
    steps.value[5].title = getStepTitle('supplementEnglish') // 先扩充英文
    steps.value[6].title = getStepTitle('expandChinese') // 后扩充中文
    steps.value[7].title = getStepTitle('analyzing')
    // 如果是完成状态且有关键词，保持原有的完成文本（包含结果数量）
    if (steps.value[7].status === 'completed' && resultCount.value > 0) {
      steps.value[7].title = t('search.modal.completedWithResults', { count: resultCount.value })
    } else {
      steps.value[7].title = getStepTitle('completed')
    }
  }
})

// 设置搜索结果（供父组件调用）
const setSearchResults = (results: Array<{ title: string; url: string }>) => {
  searchResults.value = results
}

// 获取域名名称
const getDomainName = (url: string): string => {
  if (!url) return ''
  try {
    const domain = new URL(url).hostname.replace('www.', '')
    return domain
  } catch {
    return url
  }
}

// 监听visible变化，只在首次打开时重置状态（不在重新打开时重置）
let isFirstOpen = true
watch(() => props.visible, (newVal) => {
  if (newVal && isFirstOpen) {
    // 只在第一次打开时重置
    reset()
    isFirstOpen = false
  } else if (!newVal) {
    // 关闭时标记，下次打开时需要重置（如果是新的搜索）
    // 这里不重置 isFirstOpen，让它保持 false，这样重新打开时不会重置状态
  }
})

// 暴露方法用于外部标记新的搜索开始
const markNewSearch = () => {
  isFirstOpen = true
}

// 标记综合信息步骤完成（供父组件调用）
const markSynthesizingComplete = () => {
  const synthesizingStepIndex = 13
  if (steps.value[synthesizingStepIndex]) {
    steps.value[synthesizingStepIndex].status = 'completed'
    searchCompleted.value = true
    // 完成所有步骤
    steps.value.forEach((s) => {
      if (s.status === 'active') {
        s.status = 'completed'
      }
    })
    // 注意：不启动新的倒计时，使用已启动的10秒倒计时
  }
}

// 暴露方法供父组件调用
defineExpose({
  updateProgress,
  reset,
  setSearchResults,
  markNewSearch,
  markSynthesizingComplete
})
</script>

<style scoped>
.search-progress-modal :deep(.ant-modal-content) {
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.search-progress-modal :deep(.ant-modal-body) {
  padding: 0;
}

.search-progress-container {
  display: flex;
  flex-direction: column;
  min-height: 600px;
  max-height: 90vh;
  background: #ffffff;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 32px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: white;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  font-size: 24px;
}

.title-text {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

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
}

.close-button:hover {
  background: #f5f5f5;
  color: #1a1a1a;
}

.close-button span {
  font-size: 24px;
  line-height: 1;
}

.search-query {
  display: flex;
  align-items: center;
  padding: 20px 32px 16px;
  background: white;
}

.query-text {
  font-size: 16px;
  color: #1a1a1a;
  font-weight: 500;
  flex: 1;
}

.search-results {
  padding: 20px 32px 24px;
  background: #fafafa;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.results-title {
  font-size: 14px;
  color: #1a1a1a;
  font-weight: 600;
}

.results-count {
  font-size: 12px;
  color: #8c8c8c;
  background: white;
  padding: 4px 12px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.results-list-container {
  height: 180px;
  overflow-y: auto;
  overflow-x: hidden;
  border-radius: 12px;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.results-list {
  display: flex;
  flex-direction: column;
}

.result-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  text-decoration: none;
  color: inherit;
  background: white;
  cursor: pointer;
  position: relative;
}

.result-item:last-child {
  border-bottom: none;
}

.result-item:hover {
  background: #f8f9fa;
}

.result-number {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background: #f0f0f0;
  color: #8c8c8c;
  font-size: 11px;
  font-weight: 600;
  transition: all 0.2s;
}

.result-item:hover .result-number {
  background: #e6f7ff;
  color: #1890ff;
}

.result-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.result-title-text {
  color: #262626;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
  word-break: break-word;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  transition: color 0.2s;
}

.result-item:hover .result-title-text {
  color: #1890ff;
}

.result-domain {
  color: #999;
  font-size: 10px;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'Consolas', 'Monaco', monospace;
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
}

.progress-step.step-completed {
  opacity: 1;
}

.progress-step.step-active {
  opacity: 1;
  animation: fadeIn 0.5s ease;
}

.progress-step.step-pending {
  opacity: 0.4;
}

.step-timeline {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 24px;
  flex-shrink: 0;
}

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
}

.check-icon {
  width: 16px;
  height: 16px;
  color: #52c41a;
  animation: checkmark 0.4s ease;
}

.check-path {
  stroke-dasharray: 20;
  stroke-dashoffset: 20;
  animation: drawCheck 0.4s ease forwards;
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

.progress-step.step-completed .timeline-dot {
  border-color: #52c41a;
  background: #f6ffed;
}

.progress-step.step-active .timeline-dot {
  border-color: #1890ff;
  background: #e6f7ff;
}

.step-content {
  flex: 1;
  padding-top: 2px;
}

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

.step-result {
  font-size: 13px;
  color: #595959;
  margin-top: 8px;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 6px;
  line-height: 1.6;
}

.progress-step.step-completed .step-content .step-title {
  color: #52c41a;
}

.progress-step.step-active .step-content .step-title {
  color: #1890ff;
}

.progress-footer {
  padding: 24px 32px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  background: white;
}

.result-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
}

.result-icon {
  font-size: 20px;
}

.result-text {
  font-size: 15px;
  color: #52c41a;
  font-weight: 500;
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

