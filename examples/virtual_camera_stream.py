"""
虚拟摄像头流式推送
将数字人视频实时推送到虚拟摄像头，供 Jitsi/Zoom/Teams 使用

需要安装：
- Linux: v4l2loopback
- Windows: OBS Virtual Camera
- macOS: CamTwist 或 OBS
"""
import asyncio
import cv2
import numpy as np
import aiohttp
from pathlib import Path


class VirtualCameraStreamer:
    """虚拟摄像头推流器"""
    
    def __init__(self, 
                 avatar_api_url: str = "http://localhost:8000",
                 virtual_camera_index: int = 10):
        """
        初始化
        
        Args:
            avatar_api_url: 数字人 API 地址
            virtual_camera_index: 虚拟摄像头设备索引
        """
        self.avatar_api_url = avatar_api_url
        self.virtual_camera_index = virtual_camera_index
        self.session_id = None
        self.camera = None
        
    async def setup_virtual_camera(self):
        """
        设置虚拟摄像头
        
        Linux:
            sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="AvatarCam"
        
        Windows:
            安装 OBS Studio，启用 Virtual Camera
        """
        import platform
        
        system = platform.system()
        
        if system == "Linux":
            # Linux: v4l2loopback
            device_path = f"/dev/video{self.virtual_camera_index}"
            
            # 检查设备是否存在
            if not Path(device_path).exists():
                print(f"虚拟摄像头设备 {device_path} 不存在")
                print("请运行: sudo modprobe v4l2loopback devices=1 video_nr=10")
                return False
            
            # 使用 OpenCV 打开虚拟摄像头（写入模式）
            # 注意：需要使用 ffmpeg 或 v4l2-ctl 写入
            self.camera = None  # OpenCV 不直接支持写入 v4l2loopback
            
            print(f"✓ Linux 虚拟摄像头: {device_path}")
            print("将使用 ffmpeg 推流")
            return True
            
        elif system == "Windows":
            # Windows: OBS Virtual Camera
            print("✓ Windows: 请确保 OBS Virtual Camera 已安装并启动")
            print("建议使用 OBS Studio 的 Virtual Camera 功能")
            return True
            
        elif system == "Darwin":
            # macOS: CamTwist 或 OBS
            print("✓ macOS: 请安装 CamTwist 或 OBS Virtual Camera")
            return True
            
        return False
    
    async def start_ffmpeg_stream(self):
        """
        使用 ffmpeg 推流到虚拟摄像头（Linux）
        """
        import subprocess
        
        device_path = f"/dev/video{self.virtual_camera_index}"
        
        # ffmpeg 命令：从 stdin 读取视频帧，推流到虚拟摄像头
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', '640x480',
            '-r', '25',
            '-i', '-',
            '-f', 'v4l2',
            '-pix_fmt', 'yuv420p',
            device_path
        ]
        
        self.ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print(f"✓ FFmpeg 推流已启动: {device_path}")
    
    async def push_frame(self, frame: np.ndarray):
        """
        推送一帧到虚拟摄像头
        
        Args:
            frame: OpenCV 格式的视频帧 (H, W, 3)
        """
        if self.ffmpeg_process:
            # 调整帧大小为 640x480
            frame_resized = cv2.resize(frame, (640, 480))
            
            # 写入 ffmpeg stdin
            try:
                self.ffmpeg_process.stdin.write(frame_resized.tobytes())
            except BrokenPipeError:
                print("FFmpeg 进程已关闭")
    
    async def stream_avatar_video(self, video_bytes: bytes):
        """
        推送数字人视频到虚拟摄像头
        
        Args:
            video_bytes: MP4 视频字节数据
        """
        import tempfile
        
        # 保存临时视频文件
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name
        
        # 使用 OpenCV 读取视频
        cap = cv2.VideoCapture(tmp_path)
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # 推送帧到虚拟摄像头
            await self.push_frame(frame)
            
            # 控制帧率（25 fps = 40ms per frame）
            await asyncio.sleep(0.04)
        
        cap.release()
        Path(tmp_path).unlink()  # 删除临时文件
    
    async def run_idle_animation(self):
        """
        空闲时播放默认动画（避免黑屏）
        """
        # 创建一个简单的背景帧
        idle_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 添加文字
        cv2.putText(
            idle_frame,
            "AI Avatar Ready",
            (150, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (255, 255, 255),
            2
        )
        
        # 循环推送空闲帧
        while True:
            await self.push_frame(idle_frame)
            await asyncio.sleep(0.04)
    
    async def main_loop(self):
        """主循环：接收数字人视频并推流"""
        
        # 1. 创建会话
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.avatar_api_url}/api/v1/sessions",
                json={"config": {}}
            ) as resp:
                data = await resp.json()
                self.session_id = data["session_id"]
                print(f"✓ 会话创建: {self.session_id}")
        
        # 2. 启动虚拟摄像头
        if not await self.setup_virtual_camera():
            return
        
        await self.start_ffmpeg_stream()
        
        # 3. 空闲动画任务
        idle_task = asyncio.create_task(self.run_idle_animation())
        
        print("\n虚拟摄像头已准备就绪！")
        print("现在可以在 Jitsi/Zoom/Teams 中选择虚拟摄像头")
        print("\n输入文本让数字人说话（输入 'quit' 退出）：\n")
        
        try:
            while True:
                # 从命令行读取输入（实际应用中应该从会议音频获取）
                text = await asyncio.to_thread(input, "> ")
                
                if text.lower() == 'quit':
                    break
                
                # 暂停空闲动画
                idle_task.cancel()
                
                # 调用数字人 API
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.avatar_api_url}/api/v1/sessions/{self.session_id}/text",
                        json={"text": text, "streaming": False}
                    ) as resp:
                        # 获取视频
                        video_url = (await resp.json()).get("video_url")
                        
                        # 下载视频
                        async with session.get(
                            f"{self.avatar_api_url}{video_url}"
                        ) as video_resp:
                            video_bytes = await video_resp.read()
                            
                            # 推流到虚拟摄像头
                            await self.stream_avatar_video(video_bytes)
                
                # 恢复空闲动画
                idle_task = asyncio.create_task(self.run_idle_animation())
                
        except KeyboardInterrupt:
            print("\n正在退出...")
        finally:
            idle_task.cancel()
            
            # 清理资源
            if self.ffmpeg_process:
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.wait()
            
            # 删除会话
            async with aiohttp.ClientSession() as session:
                await session.delete(
                    f"{self.avatar_api_url}/api/v1/sessions/{self.session_id}"
                )
            
            print("✓ 清理完成")


async def main():
    """主函数"""
    streamer = VirtualCameraStreamer(
        avatar_api_url="http://localhost:8000",
        virtual_camera_index=10
    )
    
    await streamer.main_loop()


if __name__ == "__main__":
    print("=" * 60)
    print("数字人虚拟摄像头推流器")
    print("=" * 60)
    print("\n准备工作（Linux）：")
    print("1. 安装 v4l2loopback:")
    print("   sudo apt install v4l2loopback-dkms")
    print("2. 加载虚拟摄像头:")
    print("   sudo modprobe v4l2loopback devices=1 video_nr=10 card_label='AvatarCam'")
    print("3. 验证设备:")
    print("   ls /dev/video*")
    print("   v4l2-ctl --list-devices")
    print("\n准备工作（Windows）：")
    print("1. 安装 OBS Studio")
    print("2. 启动 OBS 并开启 Virtual Camera")
    print("\n" + "=" * 60 + "\n")
    
    asyncio.run(main())

