#!/usr/bin/env python3
"""
诊断工具：检查bg_video.mp4是否兼容浏览器播放
"""
import subprocess
import sys
from pathlib import Path

def check_video(video_path: str):
    """检查视频文件的兼容性"""
    path = Path(video_path)
    
    if not path.exists():
        print(f"❌ 文件不存在: {path}")
        return False
    
    print(f"✅ 文件存在: {path}")
    print(f"   大小: {path.stat().st_size / 1024 / 1024:.2f} MB")
    
    # 使用ffprobe检查视频信息
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,pix_fmt,width,height,r_frame_rate',
            '-of', 'default=noprint_wrappers=1',
            str(path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ FFprobe错误: {result.stderr}")
            return False
        
        print("\n📹 视频信息:")
        print(result.stdout)
        
        # 检查关键参数
        output = result.stdout.lower()
        
        issues = []
        if 'codec_name=h264' not in output:
            issues.append("编码格式不是H.264")
        
        if 'pix_fmt=yuv420p' not in output:
            issues.append("像素格式不是yuv420p（浏览器兼容格式）")
        
        if issues:
            print("\n⚠️  兼容性问题:")
            for issue in issues:
                print(f"   - {issue}")
            print("\n建议转换命令:")
            output_path = path.parent / f"{path.stem}_web{path.suffix}"
            print(f"   ffmpeg -i {path} -c:v libx264 -pix_fmt yuv420p -movflags faststart {output_path}")
            return False
        else:
            print("\n✅ 视频格式兼容浏览器播放")
            return True
            
    except FileNotFoundError:
        print("❌ 未找到ffprobe，请安装FFmpeg")
        return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False

if __name__ == "__main__":
    video_path = sys.argv[1] if len(sys.argv) > 1 else "models/lite_avatar/default/bg_video.mp4"
    
    print(f"检查视频文件: {video_path}\n")
    check_video(video_path)
