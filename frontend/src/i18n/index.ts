import { createI18n } from 'vue-i18n'
import zh from './locales/zh'
import en from './locales/en'

// 从 localStorage 获取保存的语言，默认中文
const savedLocale = localStorage.getItem('language') || 'zh'

const i18n = createI18n({
  legacy: false, // 使用 Composition API
  locale: savedLocale,
  fallbackLocale: 'zh',
  messages: {
    zh,
    en
  }
})

export default i18n

