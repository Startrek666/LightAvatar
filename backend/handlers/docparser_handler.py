import httpx
import asyncio
from typing import Optional
from loguru import logger

class DocParserHandler:
    """文档解析处理器"""
    
    def __init__(self, api_key: str, api_url: str = "https://api-utils.lemomate.com/docparser"):
        self.api_key = api_key
        self.api_url = api_url
        self.headers = {"X-API-Key": api_key}
    
    async def submit_document(self, file_content: bytes, filename: str) -> str:
        """提交文档文件，获取任务ID"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {"file": (filename, file_content)}
                response = await client.post(
                    f"{self.api_url}/queue-task",
                    headers=self.headers,
                    files=files
                )
                
                if response.status_code != 202:
                    raise Exception(f"提交文档失败: {response.status_code} {response.text}")
                
                data = response.json()
                task_id = data.get("task_id")
                logger.info(f"[DocParser] 文档已提交，任务ID: {task_id}, 文件: {filename}")
                return task_id
                
        except Exception as e:
            logger.error(f"[DocParser] 提交文档失败: {e}")
            raise
    
    async def get_task_result(self, task_id: str) -> dict:
        """查询任务结果"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_url}/get-result/{task_id}",
                    headers=self.headers
                )
                
                if response.status_code not in [200, 202]:
                    raise Exception(f"查询任务失败: {response.status_code} {response.text}")
                
                data = response.json()
                return data
                
        except Exception as e:
            logger.error(f"[DocParser] 查询任务失败: {e}")
            raise
    
    async def parse_document(self, file_content: bytes, filename: str, max_attempts: int = 30) -> str:
        """解析文档并获取文本内容（完整流程）"""
        try:
            # 第一步：提交文档
            task_id = await self.submit_document(file_content, filename)
            
            # 第二步：轮询获取结果
            for attempt in range(max_attempts):
                await asyncio.sleep(2)  # 等待2秒
                
                result = await self.get_task_result(task_id)
                status = result.get("status")
                
                if status == "completed":
                    text = result.get("text", "")
                    logger.info(f"[DocParser] 任务完成，文本长度: {len(text)} 字符")
                    return text
                elif status == "failed":
                    error = result.get("error", "未知错误")
                    raise Exception(f"文档解析失败: {error}")
                
                logger.debug(f"[DocParser] 任务处理中... ({attempt + 1}/{max_attempts})")
            
            raise Exception("文档解析超时，请稍后重试")
            
        except Exception as e:
            logger.error(f"[DocParser] 解析文档失败: {e}")
            raise
