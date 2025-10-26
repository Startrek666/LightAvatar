#!/usr/bin/env python3
"""
测试 DuckDuckGo 搜索功能
"""
import asyncio
from duckduckgo_search import DDGS

async def test_search():
    print("=== 测试 DuckDuckGo 搜索 ===\n")
    
    query = "今天有什么新闻"
    max_results = 3
    
    print(f"搜索关键词: {query}")
    print(f"最大结果数: {max_results}\n")
    
    try:
        # 方法1: 直接同步调用
        print("方法1: 直接同步调用")
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        print(f"结果数量: {len(results)}")
        
        if results:
            print("\n第一个结果:")
            print(f"  标题: {results[0].get('title', 'N/A')}")
            print(f"  URL: {results[0].get('href', 'N/A')}")
            print(f"  摘要: {results[0].get('body', 'N/A')[:100]}...")
        else:
            print("  没有返回结果")
        
        # 方法2: 使用 asyncio.to_thread
        print("\n\n方法2: 使用 asyncio.to_thread")
        results2 = await asyncio.to_thread(
            lambda: list(ddgs.text(query, max_results=max_results))
        )
        print(f"结果数量: {len(results2)}")
        
        if results2:
            print("\n第一个结果:")
            print(f"  标题: {results2[0].get('title', 'N/A')}")
            print(f"  URL: {results2[0].get('href', 'N/A')}")
            print(f"  摘要: {results2[0].get('body', 'N/A')[:100]}...")
        else:
            print("  没有返回结果")
            
        # 测试英文搜索
        print("\n\n方法3: 测试英文搜索")
        query_en = "latest news today"
        results3 = await asyncio.to_thread(
            lambda: list(ddgs.text(query_en, max_results=max_results))
        )
        print(f"结果数量: {len(results3)}")
        
        if results3:
            print("\n第一个结果:")
            print(f"  标题: {results3[0].get('title', 'N/A')}")
            print(f"  URL: {results3[0].get('href', 'N/A')}")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_search())

