<template>
  <div class="markdown-body" ref="markdownContainer" @click="handleCitationClick">
    <div v-html="renderedHtml"></div>
    
    <!-- 引用来源列表（隐藏的引用数据） -->
    <div v-if="citations.length > 0" class="citations-data" style="display: none;">
      <div v-for="(citation, index) in citations" :key="index" :data-citation-id="index + 1">
        {{ citation }}
      </div>
    </div>
    
    <!-- 引用详情浮动框 -->
    <div 
      v-if="tooltipVisible && tooltipTitle" 
      class="citation-popover"
      :style="popoverStyle"
      @click.stop>
      <div class="citation-popover-title" v-html="tooltipTitle"></div>
      <div class="citation-popover-url">
        <a :href="tooltipUrl" target="_blank" @click.stop>{{ tooltipUrl }}</a>
      </div>
      <div class="citation-popover-close" @click="tooltipVisible = false">×</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, onMounted } from 'vue'
import { marked, Renderer } from 'marked'
import hljs from 'highlight.js'

const props = defineProps<{
  content: string
}>()

const markdownContainer = ref<HTMLElement>()
const tooltipVisible = ref(false)
const tooltipTitle = ref('')
const tooltipUrl = ref('')
const popoverStyle = ref<{ top: string; left: string }>({ top: '0px', left: '0px' })
const citations = ref<Array<{ title: string; url: string }>>([])

// 提取引用信息
function extractCitations(content: string): Array<{ title: string; url: string }> {
  const citationsList: Array<{ title: string; url: string }> = []
  
  // 匹配 "参考来源：" 后面的内容（支持多种 Markdown 格式）
  // 匹配格式：**📚 参考来源：** 或 📚 参考来源： 或 参考来源：
  // 使用更宽松的正则表达式，匹配从"参考来源"到文件末尾的所有引用
  const referencesMatch = content.match(/(?:\*\*)?(?:📚\s*)?参考来源[：:]\s*(?:\*\*)?\s*\n((?:\d+\.\s*\[.*?\]\(.*?\)\s*)+)/s)
  
  if (referencesMatch) {
    const referencesText = referencesMatch[1]
    console.log('找到参考来源部分:', referencesText) // 调试日志
    
    // 匹配每个引用：[标题](URL)
    const citationRegex = /(\d+)\.\s*\[(.*?)\]\((.*?)\)/g
    let match
    
    while ((match = citationRegex.exec(referencesText)) !== null) {
      citationsList.push({
        title: match[2],
        url: match[3]
      })
      console.log(`提取引用 ${match[1]}: ${match[2]}`) // 调试日志
    }
  } else {
    console.log('未找到参考来源部分，content:', content) // 调试日志
  }
  
  console.log('提取到的引用数量:', citationsList.length) // 调试日志
  return citationsList
}

// 处理引用标记，转换为可点击的上标
function processCitations(content: string): string {
  // 先提取引用信息
  citations.value = extractCitations(content)
  
  console.log('开始处理引用标记，引用数量:', citations.value.length) // 调试日志
  
  // 保留完整的原始内容（包括参考来源部分）
  // 将 [citation:X] 转换为可点击的上标
  // 匹配 [citation:1] 或 [citation:1][citation:2] 这样的格式
  const processedContent = content.replace(/\[citation:(\d+)\]/g, (match, num) => {
    const citationIndex = parseInt(num) - 1
    console.log(`处理 ${match}, index: ${citationIndex}, 引用总数: ${citations.value.length}`) // 调试日志
    
    if (citationIndex >= 0 && citationIndex < citations.value.length) {
      const replacement = `<sup class="citation-sup" data-citation="${num}" title="点击查看来源">${num}</sup>`
      console.log(`替换为: ${replacement}`) // 调试日志
      return replacement
    }
    console.log(`保持原样: ${match}`) // 调试日志
    return match
  })
  
  return processedContent
}

// 处理引用点击事件
function handleCitationClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  const citationSup = target.closest('.citation-sup')
  
  if (citationSup) {
    const citationId = citationSup.getAttribute('data-citation')
    if (citationId) {
      const citationIndex = parseInt(citationId) - 1
      if (citationIndex >= 0 && citationIndex < citations.value.length) {
        const citation = citations.value[citationIndex]
        
        // 设置引用信息
        tooltipTitle.value = citation.title
        tooltipUrl.value = citation.url
        
        // 计算 Popover 位置（在上标上方显示）
        const rect = citationSup.getBoundingClientRect()
        const containerRect = markdownContainer.value?.getBoundingClientRect()
        
        if (containerRect) {
          // 相对于容器的位置
          const left = rect.left - containerRect.left + rect.width / 2
          const top = rect.top - containerRect.top - 10 // 上方10px
          
          popoverStyle.value = {
            left: `${Math.max(10, Math.min(left - 150, containerRect.width - 310))}px`,
            top: `${Math.max(10, top - 80)}px`
          }
        }
        
        // 显示 Popover
        nextTick(() => {
          tooltipVisible.value = true
        })
        
        event.stopPropagation()
      }
    }
  } else {
    // 点击其他地方，关闭 Popover
    if (!target.closest('.citation-popover')) {
      tooltipVisible.value = false
    }
  }
}

// 配置 marked
// 配置 marked 选项
marked.setOptions({
  breaks: true,
  gfm: true
})

// 自定义渲染器添加代码高亮
const renderer = new Renderer()
renderer.code = function(code: string, language: string | undefined) {
  if (language && hljs.getLanguage(language)) {
    try {
      const highlighted = hljs.highlight(code, { language }).value
      return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`
    } catch (err) {
      console.error('Highlight error:', err)
    }
  }
  const highlighted = hljs.highlightAuto(code).value
  return `<pre><code class="hljs">${highlighted}</code></pre>`
}

const renderedHtml = computed(() => {
  try {
    // 先处理引用标记（在 Markdown 解析前插入 HTML）
    const processedContent = processCitations(props.content)
    // 然后渲染 Markdown，明确传递配置
    return marked.parse(processedContent, { 
      renderer,
      breaks: true,
      gfm: true
    })
  } catch (error) {
    console.error('Markdown parse error:', error)
    return props.content
  }
})

// 点击外部关闭 tooltip
onMounted(() => {
  document.addEventListener('click', (e) => {
    if (markdownContainer.value && !markdownContainer.value.contains(e.target as Node)) {
      tooltipVisible.value = false
    }
  })
})
</script>

<style scoped>
/* Markdown 基础样式 */
.markdown-body {
  font-size: 14px;
  line-height: 1.6;
  word-wrap: break-word;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 600;
  line-height: 1.25;
}

.markdown-body h1 {
  font-size: 1.8em;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 0.3em;
}

.markdown-body h2 {
  font-size: 1.5em;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 0.3em;
}

.markdown-body h3 {
  font-size: 1.25em;
}

.markdown-body h4 {
  font-size: 1em;
}

.markdown-body h5 {
  font-size: 0.875em;
}

.markdown-body h6 {
  font-size: 0.85em;
  color: #6a737d;
}

.markdown-body p {
  margin-top: 0;
  margin-bottom: 10px;
}

.markdown-body ul,
.markdown-body ol {
  margin-top: 0;
  margin-bottom: 10px;
  padding-left: 2em;
}

.markdown-body li {
  margin-bottom: 4px;
}

.markdown-body code {
  padding: 0.2em 0.4em;
  margin: 0;
  font-size: 85%;
  background-color: rgba(27, 31, 35, 0.05);
  border-radius: 3px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}

.markdown-body pre {
  padding: 16px;
  overflow: auto;
  font-size: 85%;
  line-height: 1.45;
  background-color: #f6f8fa;
  border-radius: 6px;
  margin-bottom: 16px;
}

.markdown-body pre code {
  display: inline;
  max-width: auto;
  padding: 0;
  margin: 0;
  overflow: visible;
  line-height: inherit;
  word-wrap: normal;
  background-color: transparent;
  border: 0;
}

.markdown-body blockquote {
  padding: 0 1em;
  color: #6a737d;
  border-left: 0.25em solid #dfe2e5;
  margin: 0 0 16px 0;
}

.markdown-body table {
  border-spacing: 0;
  border-collapse: collapse;
  margin-bottom: 16px;
  width: 100%;
  overflow: auto;
}

.markdown-body table th {
  font-weight: 600;
  padding: 6px 13px;
  border: 1px solid #dfe2e5;
  background-color: #f6f8fa;
}

.markdown-body table td {
  padding: 6px 13px;
  border: 1px solid #dfe2e5;
}

.markdown-body table tr {
  background-color: #fff;
  border-top: 1px solid #c6cbd1;
}

.markdown-body table tr:nth-child(2n) {
  background-color: #f6f8fa;
}

.markdown-body a {
  color: #0366d6;
  text-decoration: none;
}

.markdown-body a:hover {
  text-decoration: underline;
}

.markdown-body strong {
  font-weight: 600;
}

.markdown-body em {
  font-style: italic;
}

.markdown-body hr {
  height: 0.25em;
  padding: 0;
  margin: 24px 0;
  background-color: #e1e4e8;
  border: 0;
}

/* 代码高亮样式 */
.markdown-body .hljs {
  display: block;
  overflow-x: auto;
  padding: 0.5em;
  background: #f6f8fa;
}

.markdown-body .hljs-comment,
.markdown-body .hljs-quote {
  color: #6a737d;
  font-style: italic;
}

.markdown-body .hljs-keyword,
.markdown-body .hljs-selector-tag,
.markdown-body .hljs-subst {
  color: #d73a49;
  font-weight: bold;
}

.markdown-body .hljs-number,
.markdown-body .hljs-literal,
.markdown-body .hljs-variable,
.markdown-body .hljs-template-variable,
.markdown-body .hljs-tag .hljs-attr {
  color: #005cc5;
}

.markdown-body .hljs-string,
.markdown-body .hljs-doctag {
  color: #032f62;
}

.markdown-body .hljs-title,
.markdown-body .hljs-section,
.markdown-body .hljs-selector-id {
  color: #6f42c1;
  font-weight: bold;
}

.markdown-body .hljs-type,
.markdown-body .hljs-class .hljs-title {
  color: #445588;
  font-weight: bold;
}

.markdown-body .hljs-tag,
.markdown-body .hljs-name,
.markdown-body .hljs-attribute {
  color: #000080;
  font-weight: normal;
}

.markdown-body .hljs-regexp,
.markdown-body .hljs-link {
  color: #009926;
}

.markdown-body .hljs-symbol,
.markdown-body .hljs-bullet {
  color: #990073;
}

.markdown-body .hljs-built_in,
.markdown-body .hljs-builtin-name {
  color: #0086b3;
}

.markdown-body .hljs-meta {
  color: #999;
  font-weight: bold;
}

.markdown-body .hljs-deletion {
  background: #fdd;
}

.markdown-body .hljs-addition {
  background: #dfd;
}

.markdown-body .hljs-emphasis {
  font-style: italic;
}

.markdown-body .hljs-strong {
  font-weight: bold;
}

/* 引用上标样式 */
.markdown-body .citation-sup {
  display: inline-block;
  vertical-align: super;
  font-size: 0.75em;
  color: #1890ff;
  background-color: #e6f7ff;
  border: 1px solid #91d5ff;
  border-radius: 3px;
  padding: 2px 4px;
  margin: 0 2px;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 600;
  line-height: 1;
  text-decoration: none;
}

.markdown-body .citation-sup:hover {
  background-color: #bae7ff;
  border-color: #69c0ff;
  color: #0050b3;
  transform: scale(1.1);
}

.markdown-body .citation-sup:active {
  transform: scale(0.95);
}

/* 引用详情浮动框样式 */
.citation-popover {
  position: absolute;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 12px 16px;
  min-width: 280px;
  max-width: 400px;
  z-index: 1000;
  animation: fadeIn 0.2s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.citation-popover-title {
  font-weight: 600;
  color: #1890ff;
  margin-bottom: 8px;
  font-size: 14px;
  line-height: 1.5;
  padding-right: 20px;
}

.citation-popover-url {
  font-size: 12px;
  color: #666;
  word-break: break-all;
  margin-bottom: 4px;
}

.citation-popover-url a {
  color: #1890ff;
  text-decoration: none;
}

.citation-popover-url a:hover {
  text-decoration: underline;
}

.citation-popover-close {
  position: absolute;
  top: 8px;
  right: 12px;
  font-size: 20px;
  color: #999;
  cursor: pointer;
  line-height: 1;
  transition: color 0.2s;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.citation-popover-close:hover {
  color: #333;
}

.markdown-body {
  position: relative;
}
</style>
