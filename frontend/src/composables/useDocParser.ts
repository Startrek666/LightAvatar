import { ref } from 'vue'
import { message } from 'ant-design-vue'

// 调用自己的后端 API，不直接调用外部 API，保护 API Key
const BACKEND_API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface ParseResponse {
  success: boolean
  filename: string
  text: string
  text_length: number
}

export function useDocParser() {
  const isUploading = ref(false)
  const uploadProgress = ref(0)

  /**
   * 解析文档并获取文本内容
   * 通过自己的后端 API 代理，API Key 不会暴露给前端
   */
  const parseDocument = async (file: File): Promise<string> => {
    try {
      isUploading.value = true
      uploadProgress.value = 10

      console.log('📄 开始上传文档:', file.name, '大小:', (file.size / 1024 / 1024).toFixed(2), 'MB')
      
      // 准备 FormData
      const formData = new FormData()
      formData.append('file', file)
      
      uploadProgress.value = 20
      message.loading('正在解析文档，请稍候...', 0)

      // 调用自己的后端 API
      const response = await fetch(`${BACKEND_API}/api/docparser/parse`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: '未知错误' }))
        throw new Error(error.detail || `解析失败: ${response.status}`)
      }

      const data: ParseResponse = await response.json()
      
      uploadProgress.value = 100
      message.destroy()
      console.log('✅ 文档解析完成，文本长度:', data.text_length, '字符')
      
      return data.text
    } catch (error: any) {
      message.destroy()
      console.error('❌ 文档解析失败:', error)
      throw error
    } finally {
      isUploading.value = false
      uploadProgress.value = 0
    }
  }

  return {
    isUploading,
    uploadProgress,
    parseDocument
  }
}
