/**
 * 认证工具函数
 */

/**
 * 检查token是否有效（不验证过期，只检查是否存在）
 */
export function hasToken(): boolean {
  return !!localStorage.getItem('auth_token')
}

/**
 * 清理认证信息
 */
export function clearAuth(): void {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user_info')
}

/**
 * 跳转到登录页
 */
export function redirectToLogin(): void {
  clearAuth()
  setTimeout(() => {
    window.location.href = '/login'
  }, 300)
}

/**
 * 检查WebSocket关闭原因是否是token无效
 */
export function isTokenInvalidReason(reason: string): boolean {
  if (!reason) return false
  
  const invalidKeywords = [
    'token无效',
    '未授权',
    '认证失败',
    'Unauthorized',
    'Invalid token',
    'token过期',
    'token expired',
    '无效的认证凭据'
  ]
  
  return invalidKeywords.some(keyword => reason.includes(keyword))
}

