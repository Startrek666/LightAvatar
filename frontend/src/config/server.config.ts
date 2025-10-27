/**
 * 服务器节点配置
 */

export interface ServerNode {
  id: string;
  name: string;
  displayName: string;
  shortName: string; // 简短名称，用于移动端显示
  host: string;
  region: string;
  description: string;
  icon: string;
  priority: number; // 优先级，数字越小越优先
}

export const SERVER_NODES: ServerNode[] = [
  {
    id: 'japan',
    name: 'Japan Edge',
    displayName: '日本节点',
    shortName: 'JP',
    host: 'japan.digitalh.lemomate.com',
    region: 'jp',
    description: '优化路线，适合亚洲用户',
    icon: '🇯🇵',
    priority: 1
  },
  {
    id: 'us',
    name: 'US Origin',
    displayName: '原始节点',
    shortName: 'US',
    host: 'digitalh.lemomate.com',
    region: 'us',
    description: '美国服务器，全球默认节点',
    icon: '🇺🇸',
    priority: 2
  }
];

/**
 * 检测用户是否在中国大陆
 */
export function isChineseMainland(): boolean {
  try {
    // 方法1: 检查语言设置
    const lang = navigator.language.toLowerCase();
    const isChineseLang = lang.startsWith('zh-cn') || lang === 'zh';
    
    // 方法2: 检查时区
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const isChineseTimezone = timezone === 'Asia/Shanghai' || 
                              timezone === 'Asia/Chongqing' || 
                              timezone === 'Asia/Harbin' ||
                              timezone === 'Asia/Urumqi';
    
    // 如果语言是中文或时区是中国，则认为是中国大陆用户
    return isChineseLang || isChineseTimezone;
  } catch (error) {
    console.warn('Failed to detect user location:', error);
    return false;
  }
}

/**
 * 自动选择最优节点
 */
export function getOptimalNode(): ServerNode {
  const savedNodeId = localStorage.getItem('selected_server_node');
  
  // 如果用户手动选择过节点，优先使用用户选择
  if (savedNodeId) {
    const savedNode = SERVER_NODES.find(node => node.id === savedNodeId);
    if (savedNode) {
      console.log(`使用用户选择的节点: ${savedNode.displayName}`);
      return savedNode;
    }
  }
  
  // 自动检测：中国大陆用户使用日本节点，其他用户使用美国节点
  if (isChineseMainland()) {
    const japanNode = SERVER_NODES.find(node => node.id === 'japan');
    if (japanNode) {
      console.log('自动选择: 日本节点（检测到中国大陆用户）');
      return japanNode;
    }
  }
  
  // 默认使用美国节点
  const usNode = SERVER_NODES.find(node => node.id === 'us');
  if (usNode) {
    console.log('自动选择: 美国节点（默认）');
    return usNode;
  }
  
  // 兜底：使用第一个节点
  return SERVER_NODES[0];
}

/**
 * 获取 API Base URL
 */
export function getApiBaseUrl(node?: ServerNode): string {
  const targetNode = node || getOptimalNode();
  const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
  return `${protocol}//${targetNode.host}`;
}

/**
 * 获取 WebSocket URL
 */
export function getWebSocketUrl(path: string, node?: ServerNode): string {
  const targetNode = node || getOptimalNode();
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${targetNode.host}${path}`;
}

/**
 * 保存用户选择的节点
 */
export function saveSelectedNode(nodeId: string): void {
  localStorage.setItem('selected_server_node', nodeId);
  console.log(`已保存节点选择: ${nodeId}`);
}

/**
 * 清除节点选择（使用自动检测）
 */
export function clearSelectedNode(): void {
  localStorage.removeItem('selected_server_node');
  console.log('已清除节点选择，将自动检测');
}

/**
 * 获取当前选择的节点（包括手动选择和自动检测）
 */
export function getCurrentNode(): ServerNode {
  return getOptimalNode();
}

