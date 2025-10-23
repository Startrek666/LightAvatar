### 5.api调用

在所有请求的 HTTP Header 中加入 `X-API-Key`。

*   **Header**: X-API-Key: L5kGzmjwqXbk0ViD@

---

### **第一步：提交文件，获取任务ID**

向服务器上传文档文件，服务器会立即返回一个任务ID。

*   **Endpoint**: `https://api-utils.lemomate.com/docparser/queue-task`
*   **Method**: `POST`
*   **Body**: `multipart/form-data`
    *   **`file`**: 上传的文档文件。

#### **示例 **
```bash
# 将 /path/to/your/document.docx 替换为本地文件路径
curl -X POST "https://api-utils.lemomate.com/docparser/queue-task" \
     -H "X-API-Key: YOUR_SECRET_KEY_HERE" \
     -F "file=@/path/to/your/document.docx"
```

#### **成功响应 (202 Accepted)**
收到一个JSON对象，其中包含用于查询结果的 `task_id`。

```json
{
    "task_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
    "message": "任务已成功提交，请稍后查询结果。"
}
```

### **第二步：使用任务ID，查询提取结果**

使用上一步获得的 `task_id`，轮询（poll）此接口直到获取最终结果。

*   **Endpoint**: `https://api-utils.lemomate.com/docparser/get-result/{task_id}`
*   **Method**: `GET`

#### **示例 **
```bash
curl "https://api-utils.lemomate.com/docparser/get-result/a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6" \
     -H "X-API-Key: YOUR_SECRET_KEY_HERE"
```

#### **响应**

*   **如果任务仍在处理中 (202 Accepted):**
    ```json
    {
        "task_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
        "status": "pending"
    }
    ```
    **=> 等待几秒钟后再次请求。**

*   **如果任务已完成 (200 OK):**
    ```json
    {
        "task_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
        "status": "completed",
        "text": "这是从文档中提取的所有文本内容...\n包括段落和表格中的文字。\n表格的同一行单元格会用制表符\t分隔。"
    }
    ```