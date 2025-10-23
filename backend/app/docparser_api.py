"""
文档解析 API - 代理 docparser 服务，保护 API Key
"""
from fastapi import APIRouter, File, UploadFile, HTTPException
from loguru import logger

from backend.app.config import settings
from backend.handlers.docparser_handler import DocParserHandler

router = APIRouter(prefix="/api/docparser", tags=["Document Parser"])

# 初始化 DocParser Handler
# API Key 从环境变量或配置文件读取，不暴露给前端
docparser_handler = DocParserHandler(
    api_key=getattr(settings, 'DOCPARSER_API_KEY', 'L5kGzmjwqXbk0ViD@')
)


@router.post("/parse")
async def parse_document(file: UploadFile = File(...)):
    """
    上传并解析文档
    
    - 支持格式: PDF, DOCX, PPTX
    - 最大文件大小: 30MB
    - 返回: 文档提取的文本内容
    """
    try:
        # 验证文件类型
        allowed_types = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ]
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail="仅支持 PDF、DOCX、PPTX 格式的文件"
            )
        
        # 读取文件内容
        file_content = await file.read()
        
        # 验证文件大小（30MB）
        max_size = 30 * 1024 * 1024
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail="文件大小不能超过 30MB"
            )
        
        logger.info(f"[DocParser API] 收到文档: {file.filename}, 大小: {len(file_content)} 字节")
        
        # 调用 docparser handler 解析文档
        text = await docparser_handler.parse_document(file_content, file.filename)
        
        logger.info(f"[DocParser API] 文档解析成功: {file.filename}, 文本长度: {len(text)} 字符")
        
        return {
            "success": True,
            "filename": file.filename,
            "text": text,
            "text_length": len(text)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DocParser API] 解析文档失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"文档解析失败: {str(e)}"
        )
