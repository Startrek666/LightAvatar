#!/usr/bin/env python3
"""
测试 DuckDuckGo 搜索功能
"""
import asyncio
try:
    from ddgs import DDGS
    print("✅ 使用新包: ddgs")
except ImportError:
    from duckduckgo_search import DDGS
    print("⚠️ 使用旧包: duckduckgo-search (建议升级)")

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
            
        # 测试带地区参数的中文搜索
        print("\n\n方法3: 测试带优化参数的搜索")
        results3 = await asyncio.to_thread(
            lambda: list(ddgs.text(
                query=query,  # 参数名是 query
                max_results=max_results, 
                region='cn-zh',
                safesearch='moderate',
                timelimit='m'  # 最近一个月
            ))
        )
        print(f"结果数量: {len(results3)}")
        
        if results3:
            print("\n前3个结果:")
            for i, r in enumerate(results3[:3], 1):
                print(f"\n结果 {i}:")
                print(f"  标题: {r.get('title', 'N/A')}")
                print(f"  URL: {r.get('href', 'N/A')}")
                print(f"  摘要: {r.get('body', 'N/A')[:80]}...")
        
        # 测试关键词优化（开源大模型）
        print("\n\n方法4: 测试关键词优化 - 开源大模型")
        query_llm = "最近有什么开源大模型"
        # 模拟关键词优化
        optimized_query_llm = f"{query_llm} open source LLM"
        print(f"原查询: {query_llm}")
        print(f"优化后: {optimized_query_llm}")
        
        results4 = await asyncio.to_thread(
            lambda: list(ddgs.text(
                query=optimized_query_llm,
                max_results=max_results,
                region='cn-zh',
                timelimit='m'
            ))
        )
        print(f"结果数量: {len(results4)}")
        
        if results4:
            print("\n前3个结果:")
            for i, r in enumerate(results4[:3], 1):
                print(f"\n结果 {i}:")
                print(f"  标题: {r.get('title', 'N/A')[:70]}...")
                print(f"  URL: {r.get('href', 'N/A')}")
        
        # 测试英文搜索
        print("\n\n方法5: 测试英文搜索")
        query_en = "latest news today"
        results5 = await asyncio.to_thread(
            lambda: list(ddgs.text(query_en, max_results=max_results))
        )
        print(f"结果数量: {len(results5)}")
        
        if results5:
            print("\n第一个结果:")
            print(f"  标题: {results5[0].get('title', 'N/A')}")
            print(f"  URL: {results5[0].get('href', 'N/A')}")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_search())

