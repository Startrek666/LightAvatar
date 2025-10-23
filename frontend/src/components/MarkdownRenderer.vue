<template>
  <div class="markdown-body" v-html="renderedHtml"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'

const props = defineProps<{
  content: string
}>()

// 配置 marked
marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch (err) {
        console.error('Highlight error:', err)
      }
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true,
  gfm: true
})

const renderedHtml = computed(() => {
  try {
    return marked.parse(props.content)
  } catch (error) {
    console.error('Markdown parse error:', error)
    return props.content
  }
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
</style>
