#!/usr/bin/env python3
"""
测试视频编码能力
检查FFmpeg和OpenCV的H.264支持
"""
import cv2
import numpy as np
import subprocess
import tempfile
from pathlib import Path

def check_ffmpeg():
    """检查FFmpeg和H.264支持"""
    print("=" * 60)
    print("检查 FFmpeg")
    print("=" * 60)
    
    try:
        # 检查FFmpeg版本
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.decode().split('\n')[0]
            print(f"✓ FFmpeg已安装: {version}")
        else:
            print("✗ FFmpeg未正确安装")
            return False
    except FileNotFoundError:
        print("✗ FFmpeg未找到，请安装:")
        print("  Ubuntu: sudo apt-get install ffmpeg")
        print("  CentOS: sudo yum install ffmpeg")
        return False
    except Exception as e:
        print(f"✗ FFmpeg检查失败: {e}")
        return False
    
    try:
        # 检查H.264编码器
        result = subprocess.run(['ffmpeg', '-codecs'], capture_output=True, timeout=5)
        output = result.stdout.decode()
        
        if 'libx264' in output:
            print("✓ libx264 (H.264编码器) 可用")
            return True
        else:
            print("✗ libx264 不可用")
            print("  请安装: sudo apt-get install libx264-dev")
            return False
    except Exception as e:
        print(f"✗ 编码器检查失败: {e}")
        return False

def check_opencv_codecs():
    """检查OpenCV支持的编码器"""
    print("\n" + "=" * 60)
    print("检查 OpenCV 编码器")
    print("=" * 60)
    
    codecs_to_test = [
        ('avc1', 'H.264 (推荐)'),
        ('H264', 'H.264 变体'),
        ('X264', 'x264'),
        ('mp4v', 'MPEG-4'),
        ('MJPG', 'MJPEG (不推荐)')
    ]
    
    available_codecs = []
    
    for codec, desc in codecs_to_test:
        try:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            # 尝试创建一个测试视频
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                tmp_path = tmp.name
            
            writer = cv2.VideoWriter(tmp_path, fourcc, 25.0, (640, 480))
            
            if writer.isOpened():
                print(f"✓ {codec:6s} - {desc} - 可用")
                available_codecs.append(codec)
                writer.release()
            else:
                print(f"✗ {codec:6s} - {desc} - 不可用")
            
            # 清理
            Path(tmp_path).unlink(missing_ok=True)
            
        except Exception as e:
            print(f"✗ {codec:6s} - {desc} - 错误: {e}")
    
    return available_codecs

def test_encoding_pipeline():
    """测试完整的编码流程"""
    print("\n" + "=" * 60)
    print("测试编码流程")
    print("=" * 60)
    
    # 生成测试帧
    frames = []
    for i in range(10):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        frames.append(frame)
    
    print(f"生成了 {len(frames)} 个测试帧")
    
    # 测试OpenCV编码
    print("\n测试 OpenCV 编码...")
    test_opencv_encoding(frames)
    
    # 测试FFmpeg编码
    print("\n测试 FFmpeg 编码...")
    test_ffmpeg_encoding(frames)

def test_opencv_encoding(frames):
    """测试OpenCV编码"""
    try:
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
    except:
        try:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        except:
            print("✗ 无法创建编码器")
            return
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        writer = cv2.VideoWriter(tmp_path, fourcc, 25.0, (640, 480))
        
        if not writer.isOpened():
            print("✗ VideoWriter 打开失败")
            return
        
        for frame in frames:
            writer.write(frame)
        
        writer.release()
        
        # 检查文件大小
        file_size = Path(tmp_path).stat().st_size
        
        if file_size > 0:
            print(f"✓ OpenCV编码成功: {file_size} bytes")
            
            # 检查是否能被浏览器播放（检查编码格式）
            check_browser_compatibility(tmp_path)
        else:
            print("✗ 生成的视频文件为空")
    
    except Exception as e:
        print(f"✗ OpenCV编码失败: {e}")
    
    finally:
        Path(tmp_path).unlink(missing_ok=True)

def test_ffmpeg_encoding(frames):
    """测试FFmpeg编码"""
    try:
        height, width = frames[0].shape[:2]
        
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-s', f'{width}x{height}', '-pix_fmt', 'bgr24', '-r', '25',
            '-i', '-', '-c:v', 'libx264', '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-crf', '23', '-pix_fmt', 'yuv420p', 
            '-movflags', 'frag_keyframe+empty_moov',  # 支持pipe输出
            '-f', 'mp4', 'pipe:1'
        ]
        
        print(f"FFmpeg命令: {' '.join(ffmpeg_cmd)}")
        
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Prepare all frame data
        try:
            input_data = b''.join(frame.tobytes() for frame in frames)
            print(f"  准备数据: {len(input_data)} bytes ({len(frames)} 帧)")
        except Exception as e:
            print(f"✗ 准备帧数据失败: {e}")
            process.kill()
            return
        
        # Send data and get output
        try:
            print("  发送数据到FFmpeg...")
            video_bytes, stderr = process.communicate(input=input_data, timeout=30)
        except BrokenPipeError as e:
            print(f"✗ FFmpeg broken pipe错误: {e}")
            # 获取stderr查看错误
            try:
                _, stderr = process.communicate()
                if stderr:
                    print(f"  FFmpeg stderr:\n{stderr.decode()}")
            except:
                pass
            process.kill()
            return
        
        print(f"  FFmpeg返回码: {process.returncode}")
        print(f"  输出大小: {len(video_bytes)} bytes")
        
        if stderr:
            stderr_text = stderr.decode()
            # 只打印最后几行（通常包含关键错误）
            stderr_lines = stderr_text.strip().split('\n')
            if len(stderr_lines) > 5:
                print(f"  FFmpeg stderr (最后5行):")
                for line in stderr_lines[-5:]:
                    print(f"    {line}")
            else:
                print(f"  FFmpeg stderr:\n{stderr_text}")
        
        if process.returncode == 0 and len(video_bytes) > 0:
            print(f"✓ FFmpeg编码成功: {len(video_bytes)} bytes")
            
            # 保存测试文件
            test_file = Path('/tmp/test_ffmpeg_output.mp4')
            test_file.write_bytes(video_bytes)
            print(f"  测试文件已保存: {test_file}")
        else:
            print(f"✗ FFmpeg编码失败 (returncode: {process.returncode})")
    
    except FileNotFoundError:
        print("✗ FFmpeg未找到")
    except Exception as e:
        print(f"✗ FFmpeg编码失败: {e}")
        import traceback
        traceback.print_exc()

def check_browser_compatibility(video_path):
    """检查视频是否兼容浏览器"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=codec_name', '-of', 'default=noprint_wrappers=1:nokey=1',
             video_path],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0:
            codec = result.stdout.decode().strip()
            if codec == 'h264':
                print(f"  ✓ 编码格式: {codec} (浏览器兼容)")
            else:
                print(f"  ⚠ 编码格式: {codec} (浏览器可能不支持)")
        
    except FileNotFoundError:
        pass  # ffprobe不可用
    except Exception:
        pass

def print_recommendations():
    """打印推荐配置"""
    print("\n" + "=" * 60)
    print("推荐配置")
    print("=" * 60)
    print("""
Ubuntu/Debian系统:
  sudo apt-get update
  sudo apt-get install -y ffmpeg libx264-dev

CentOS/RHEL系统:
  sudo yum install -y epel-release
  sudo yum install -y ffmpeg ffmpeg-devel

如果FFmpeg不支持libx264，需要重新编译:
  https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu
""")

if __name__ == '__main__':
    print("视频编码能力测试\n")
    
    ffmpeg_ok = check_ffmpeg()
    opencv_codecs = check_opencv_codecs()
    test_encoding_pipeline()
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    if ffmpeg_ok:
        print("✓ FFmpeg with H.264: 可用 (推荐)")
    else:
        print("✗ FFmpeg with H.264: 不可用")
    
    if 'avc1' in opencv_codecs or 'H264' in opencv_codecs:
        print("✓ OpenCV H.264: 可用")
    elif opencv_codecs:
        print(f"⚠ OpenCV: 仅支持 {opencv_codecs} (可能不兼容浏览器)")
    else:
        print("✗ OpenCV: 无可用编码器")
    
    if not ffmpeg_ok:
        print_recommendations()
