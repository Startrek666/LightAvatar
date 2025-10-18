"""
LiteAvatar 集成测试脚本
验证 LiteAvatar 引擎是否正常工作
"""
import asyncio
import sys
from pathlib import Path
from loguru import logger
import wave
import struct

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.handlers.avatar.lite_avatar_handler import LiteAvatarHandler


def generate_test_audio(duration_seconds: float = 2.0, sample_rate: int = 16000) -> bytes:
    """
    生成测试音频（纯音440Hz）
    
    Args:
        duration_seconds: 音频时长（秒）
        sample_rate: 采样率
    
    Returns:
        音频字节流
    """
    import math
    
    num_samples = int(duration_seconds * sample_rate)
    frequency = 440.0  # A4音符
    
    # 生成正弦波
    audio_data = []
    for i in range(num_samples):
        value = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * i / sample_rate))
        audio_data.append(struct.pack('h', value))
    
    return b''.join(audio_data)


def read_audio_file(audio_path: Path) -> bytes:
    """
    读取音频文件
    
    Args:
        audio_path: 音频文件路径
    
    Returns:
        音频字节流（不含WAV头）
    """
    try:
        with wave.open(str(audio_path), 'rb') as wav_file:
            params = wav_file.getparams()
            logger.info(f"音频参数: {params.nchannels}声道, {params.framerate}Hz, {params.nframes}帧")
            
            # 读取音频数据（不含头）
            audio_data = wav_file.readframes(params.nframes)
            return audio_data
    except Exception as e:
        logger.error(f"读取音频文件失败: {e}")
        raise


async def test_initialization():
    """测试 LiteAvatar Handler 初始化"""
    logger.info("=" * 60)
    logger.info("测试1: 初始化")
    logger.info("=" * 60)
    
    try:
        handler = LiteAvatarHandler(
            fps=30,
            resolution=(512, 512),
            config={
                "avatar_name": "default",
                "use_gpu": False,
                "render_threads": 1,
                "bg_frame_count": 150
            }
        )
        
        logger.info("✓ LiteAvatarHandler 创建成功")
        
        # 初始化
        await handler.initialize()
        logger.info("✓ Handler 初始化成功")
        
        # 清理
        await handler.cleanup()
        logger.info("✓ Handler 清理成功")
        
        return True
        
    except FileNotFoundError as e:
        logger.error(f"✗ 文件未找到: {e}")
        logger.error("请先运行: python scripts/prepare_lite_avatar_data.py")
        return False
    except Exception as e:
        logger.error(f"✗ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_audio_processing():
    """测试音频处理"""
    logger.info("=" * 60)
    logger.info("测试2: 音频处理")
    logger.info("=" * 60)
    
    try:
        handler = LiteAvatarHandler(
            fps=30,
            resolution=(512, 512),
            config={
                "avatar_name": "default",
                "use_gpu": False,
                "render_threads": 1,
                "bg_frame_count": 50  # 减少帧数加快测试
            }
        )
        
        await handler.initialize()
        logger.info("✓ Handler 已初始化")
        
        # 生成测试音频
        audio_data = generate_test_audio(duration_seconds=1.0)
        logger.info(f"✓ 生成测试音频: {len(audio_data)} 字节")
        
        # 处理音频
        logger.info("开始处理音频...")
        video_data = await handler.process({
            "audio_data": audio_data
        })
        
        logger.info(f"✓ 生成视频: {len(video_data)} 字节 ({len(video_data) / 1024 / 1024:.2f} MB)")
        
        # 保存视频
        output_path = project_root / "test_output_lite.mp4"
        with open(output_path, 'wb') as f:
            f.write(video_data)
        logger.info(f"✓ 视频已保存: {output_path}")
        
        # 清理
        await handler.cleanup()
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 音频处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_with_real_audio():
    """测试真实音频文件"""
    logger.info("=" * 60)
    logger.info("测试3: 真实音频文件")
    logger.info("=" * 60)
    
    # 查找测试音频
    test_audio_candidates = [
        project_root / "test_audio.wav",
        project_root / "test.wav",
        project_root / "sample.wav",
    ]
    
    audio_path = None
    for candidate in test_audio_candidates:
        if candidate.exists():
            audio_path = candidate
            break
    
    if not audio_path:
        logger.warning("⚠ 未找到测试音频文件，跳过此测试")
        logger.info(f"  可以放置音频到: {test_audio_candidates[0]}")
        return None
    
    try:
        logger.info(f"使用音频文件: {audio_path}")
        
        handler = LiteAvatarHandler(
            fps=30,
            resolution=(512, 512),
            config={
                "avatar_name": "default",
                "use_gpu": False,
                "render_threads": 1,
                "bg_frame_count": 150
            }
        )
        
        await handler.initialize()
        
        # 读取音频
        audio_data = read_audio_file(audio_path)
        logger.info(f"✓ 读取音频: {len(audio_data)} 字节")
        
        # 处理
        logger.info("开始处理真实音频...")
        video_data = await handler.process({
            "audio_data": audio_data
        })
        
        logger.info(f"✓ 生成视频: {len(video_data)} 字节 ({len(video_data) / 1024 / 1024:.2f} MB)")
        
        # 保存
        output_path = project_root / "test_output_lite_real.mp4"
        with open(output_path, 'wb') as f:
            f.write(video_data)
        logger.info(f"✓ 视频已保存: {output_path}")
        
        await handler.cleanup()
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 真实音频测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_performance():
    """测试性能指标"""
    logger.info("=" * 60)
    logger.info("测试4: 性能基准")
    logger.info("=" * 60)
    
    try:
        import time
        
        handler = LiteAvatarHandler(
            fps=30,
            resolution=(512, 512),
            config={
                "avatar_name": "default",
                "use_gpu": False,
                "render_threads": 1,
                "bg_frame_count": 150
            }
        )
        
        # 初始化时间
        start = time.time()
        await handler.initialize()
        init_time = time.time() - start
        logger.info(f"✓ 初始化时间: {init_time:.2f}秒")
        
        # 处理时间（3秒音频）
        audio_data = generate_test_audio(duration_seconds=3.0)
        
        start = time.time()
        video_data = await handler.process({"audio_data": audio_data})
        process_time = time.time() - start
        
        fps_actual = (3.0 * 30) / process_time
        logger.info(f"✓ 处理时间: {process_time:.2f}秒")
        logger.info(f"✓ 实际FPS: {fps_actual:.1f} fps")
        logger.info(f"✓ 视频大小: {len(video_data) / 1024 / 1024:.2f} MB")
        
        # 内存占用
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        logger.info(f"✓ 内存占用: {memory_mb:.1f} MB")
        
        await handler.cleanup()
        
        # 性能评估
        if fps_actual >= 25:
            logger.info("✓ 性能评级: 优秀")
        elif fps_actual >= 20:
            logger.info("⚠ 性能评级: 良好")
        else:
            logger.warning("⚠ 性能评级: 需要优化")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 性能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    logger.info("LiteAvatar 集成测试")
    logger.info("=" * 60)
    
    results = {}
    
    # 测试1: 初始化
    results["initialization"] = await test_initialization()
    
    if not results["initialization"]:
        logger.error("初始化测试失败，后续测试中止")
        return
    
    # 测试2: 音频处理
    results["audio_processing"] = await test_audio_processing()
    
    # 测试3: 真实音频
    results["real_audio"] = await test_with_real_audio()
    
    # 测试4: 性能基准
    results["performance"] = await test_performance()
    
    # 总结
    logger.info("=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)
    
    for test_name, result in results.items():
        if result is True:
            status = "✓ 通过"
        elif result is False:
            status = "✗ 失败"
        else:
            status = "⚠ 跳过"
        logger.info(f"{test_name:20s}: {status}")
    
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    
    logger.info(f"\n通过: {passed}, 失败: {failed}, 跳过: {skipped}")
    
    if failed == 0:
        logger.info("✓ 所有测试通过！LiteAvatar 集成成功。")
    else:
        logger.error("✗ 部分测试失败，请检查错误信息。")


if __name__ == "__main__":
    asyncio.run(main())
