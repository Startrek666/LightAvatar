<template>
  <a-layout class="monitor-layout">
    <a-layout-header class="header">
      <h1>Avatar Chat 监控面板</h1>
      <div class="header-info">
        <a-tag :color="systemStatus.status === 'healthy' ? 'green' : 'red'">
          {{ systemStatus.status === 'healthy' ? '系统正常' : '系统异常' }}
        </a-tag>
        <span>运行时间: {{ formatUptime(systemStatus.uptime_seconds) }}</span>
      </div>
    </a-layout-header>
    
    <a-layout-content class="content">
      <!-- System Overview -->
      <a-row :gutter="16" class="overview-row">
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="活跃会话"
              :value="activeSessions"
              :suffix="`/ ${maxSessions}`"
            >
              <template #prefix>
                <UserOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="CPU 使用率"
              :value="systemInfo.cpu_percent"
              suffix="%"
              :value-style="{ color: getCPUColor(systemInfo.cpu_percent) }"
            >
              <template #prefix>
                <DashboardOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="内存使用"
              :value="(systemInfo.memory_percent || 0).toFixed(1)"
              suffix="%"
              :value-style="{ color: getMemoryColor(systemInfo.memory_percent) }"
            >
              <template #prefix>
                <DatabaseOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="请求总数"
              :value="requestCount"
            >
              <template #prefix>
                <ApiOutlined />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>
      
      <!-- Charts -->
      <a-row :gutter="16} class="charts-row">
        <a-col :span="12">
          <a-card title="CPU 使用率趋势" :bordered="false">
            <v-chart class="chart" :option="cpuChartOption" autoresize />
          </a-card>
        </a-col>
        
        <a-col :span="12">
          <a-card title="内存使用趋势" :bordered="false">
            <v-chart class="chart" :option="memoryChartOption" autoresize />
          </a-card>
        </a-col>
      </a-row>
      
      <!-- Sessions Table -->
      <a-card title="活跃会话" class="sessions-card">
        <a-table
          :columns="sessionColumns"
          :data-source="sessions"
          :pagination="false"
          row-key="session_id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'created_at'">
              {{ formatTime(record.created_at) }}
            </template>
            <template v-else-if="column.key === 'last_active'">
              {{ formatTime(record.last_active) }}
            </template>
            <template v-else-if="column.key === 'is_processing'">
              <a-tag :color="record.is_processing ? 'processing' : 'default'">
                {{ record.is_processing ? '处理中' : '空闲' }}
              </a-tag>
            </template>
          </template>
        </a-table>
      </a-card>
      
      <!-- Handler Performance -->
      <a-row :gutter="16} class="performance-row">
        <a-col :span="24}>
          <a-card title="模块性能" :bordered="false">
            <a-row :gutter="16}>
              <a-col :span="4" v-for="handler in handlers" :key="handler.name">
                <div class="handler-metric">
                  <div class="handler-name">{{ handler.name }}</div>
                  <div class="handler-time">{{ handler.avgTime }}ms</div>
                  <a-progress
                    :percent="getHandlerPercent(handler.avgTime)"
                    :stroke-color="getHandlerColor(handler.avgTime)"
                    :show-info="false"
                  />
                </div>
              </a-col>
            </a-row>
          </a-card>
        </a-col>
      </a-row>
    </a-layout-content>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { 
  UserOutlined, 
  DashboardOutlined, 
  DatabaseOutlined, 
  ApiOutlined 
} from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import axios from 'axios'

// Data
const systemStatus = ref({
  status: 'healthy',
  uptime_seconds: 0,
  issues: []
})

const systemInfo = ref({
  cpu_percent: 0,
  memory_percent: 0,
  disk_percent: 0
})

const activeSessions = ref(0)
const maxSessions = ref(10)
const requestCount = ref(0)
const sessions = ref([])

const cpuHistory = ref<number[]>([])
const memoryHistory = ref<number[]>([])
const timeLabels = ref<string[]>([])

const handlers = ref([
  { name: 'VAD', avgTime: 0 },
  { name: 'ASR', avgTime: 0 },
  { name: 'LLM', avgTime: 0 },
  { name: 'TTS', avgTime: 0 },
  { name: 'Avatar', avgTime: 0 }
])

// Table columns
const sessionColumns = [
  {
    title: '会话ID',
    dataIndex: 'session_id',
    key: 'session_id',
    ellipsis: true
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    key: 'created_at'
  },
  {
    title: '最后活跃',
    dataIndex: 'last_active',
    key: 'last_active'
  },
  {
    title: '对话轮数',
    dataIndex: 'conversation_length',
    key: 'conversation_length'
  },
  {
    title: '状态',
    dataIndex: 'is_processing',
    key: 'is_processing'
  }
]

// Chart options
const cpuChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis'
  },
  xAxis: {
    type: 'category',
    data: timeLabels.value,
    boundaryGap: false
  },
  yAxis: {
    type: 'value',
    max: 100,
    axisLabel: {
      formatter: '{value}%'
    }
  },
  series: [{
    data: cpuHistory.value,
    type: 'line',
    smooth: true,
    areaStyle: {
      opacity: 0.3
    },
    itemStyle: {
      color: '#1890ff'
    }
  }]
}))

const memoryChartOption = computed(() => ({
  tooltip: {
    trigger: 'axis'
  },
  xAxis: {
    type: 'category',
    data: timeLabels.value,
    boundaryGap: false
  },
  yAxis: {
    type: 'value',
    max: 100,
    axisLabel: {
      formatter: '{value}%'
    }
  },
  series: [{
    data: memoryHistory.value,
    type: 'line',
    smooth: true,
    areaStyle: {
      opacity: 0.3
    },
    itemStyle: {
      color: '#52c41a'
    }
  }]
}))

// Methods
const formatUptime = (seconds: number) => {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  
  if (days > 0) {
    return `${days}天 ${hours}小时`
  } else if (hours > 0) {
    return `${hours}小时 ${minutes}分钟`
  } else {
    return `${minutes}分钟`
  }
}

const formatTime = (timestamp: string) => {
  return dayjs(timestamp).format('HH:mm:ss')
}

const getCPUColor = (percent: number) => {
  if (percent > 80) return '#ff4d4f'
  if (percent > 60) return '#faad14'
  return '#52c41a'
}

const getMemoryColor = (percent: number) => {
  if (percent > 85) return '#ff4d4f'
  if (percent > 70) return '#faad14'
  return '#52c41a'
}

const getHandlerPercent = (time: number) => {
  return Math.min((time / 1000) * 100, 100)
}

const getHandlerColor = (time: number) => {
  if (time > 500) return '#ff4d4f'
  if (time > 200) return '#faad14'
  return '#52c41a'
}

// Fetch data
const fetchHealth = async () => {
  try {
    const response = await axios.get('/api/health')
    systemStatus.value = response.data
    systemInfo.value = response.data.system_info || {}
  } catch (error) {
    console.error('Failed to fetch health:', error)
  }
}

const fetchSessions = async () => {
  try {
    const response = await axios.get('/api/sessions')
    sessions.value = response.data.active_sessions || []
    activeSessions.value = sessions.value.length
  } catch (error) {
    console.error('Failed to fetch sessions:', error)
  }
}

const fetchMetrics = async () => {
  try {
    const response = await axios.get('/metrics')
    const text = response.data
    
    // Parse Prometheus metrics
    const lines = text.split('\n')
    for (const line of lines) {
      if (line.startsWith('avatar_requests_total')) {
        const match = line.match(/(\d+)$/)
        if (match) {
          requestCount.value = parseInt(match[1])
        }
      }
      
      // Parse handler metrics
      if (line.includes('avatar_vad_processing_seconds_sum')) {
        // Update handler times
      }
    }
  } catch (error) {
    console.error('Failed to fetch metrics:', error)
  }
}

const updateCharts = () => {
  // Add new data points
  const now = dayjs().format('HH:mm:ss')
  timeLabels.value.push(now)
  cpuHistory.value.push(systemInfo.value.cpu_percent)
  memoryHistory.value.push(systemInfo.value.memory_percent)
  
  // Keep only last 20 points
  if (timeLabels.value.length > 20) {
    timeLabels.value.shift()
    cpuHistory.value.shift()
    memoryHistory.value.shift()
  }
}

// Auto refresh
let refreshInterval: number

onMounted(() => {
  // Initial fetch
  fetchHealth()
  fetchSessions()
  fetchMetrics()
  
  // Set up auto refresh
  refreshInterval = setInterval(() => {
    fetchHealth()
    fetchSessions()
    fetchMetrics()
    updateCharts()
  }, 5000) // Refresh every 5 seconds
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.monitor-layout {
  height: 100vh;
}

.header {
  background: #fff;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.header h1 {
  margin: 0;
  font-size: 20px;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.content {
  padding: 24px;
  overflow-y: auto;
}

.overview-row,
.charts-row,
.performance-row {
  margin-bottom: 16px;
}

.chart {
  height: 300px;
}

.sessions-card {
  margin-bottom: 16px;
}

.handler-metric {
  text-align: center;
  padding: 16px;
}

.handler-name {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.handler-time {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
}
</style>
