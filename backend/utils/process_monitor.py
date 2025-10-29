"""
进程监控和清理工具
用于检测和清理僵尸FFmpeg进程，防止系统资源耗尽
"""
import asyncio
import psutil
import time
from pathlib import Path
from loguru import logger


class ProcessMonitor:
    """监控和清理系统进程"""
    
    def __init__(self):
        self.monitored_pids = set()
        self.last_cleanup_time = 0
    
    async def start_monitoring(self):
        """启动后台监控任务，每30秒检查一次"""
        logger.info("🔍 进程监控服务已启动")
        
        while True:
            try:
                await self.cleanup_zombie_processes()
                await self.check_system_resources()
                await asyncio.sleep(30)  # 每30秒检查一次
            except Exception as e:
                logger.error(f"进程监控失败: {e}")
                await asyncio.sleep(60)  # 出错后等待更长时间
    
    async def cleanup_zombie_processes(self):
        """清理僵尸和长时间运行的FFmpeg进程"""
        try:
            zombie_count = 0
            long_running_count = 0
            current_time = time.time()
            
            for proc in psutil.process_iter(['pid', 'name', 'status', 'create_time']):
                try:
                    info = proc.info
                    
                    # 只处理FFmpeg进程
                    if not info.get('name') or 'ffmpeg' not in info['name'].lower():
                        continue
                    
                    pid = info['pid']
                    status = info.get('status')
                    create_time = info.get('create_time', 0)
                    running_time = current_time - create_time if create_time else 0
                    
                    # 1. 清理僵尸进程
                    if status == psutil.STATUS_ZOMBIE:
                        logger.warning(f"🧟 发现僵尸FFmpeg进程 PID={pid}")
                        try:
                            proc.kill()
                            zombie_count += 1
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    # 2. 清理不可中断睡眠进程（通常是卡死）
                    elif status == 'D':  # Disk sleep (uninterruptible)
                        logger.warning(f"💀 发现卡死FFmpeg进程 PID={pid} (状态: D)")
                        try:
                            proc.kill()
                            zombie_count += 1
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    # 3. 清理运行时间超过5分钟的进程（正常FFmpeg应该20秒内完成）
                    elif running_time > 300:  # 5分钟 = 300秒
                        logger.warning(f"⏰ FFmpeg进程运行时间过长 PID={pid}, 已运行{running_time:.0f}秒")
                        try:
                            proc.kill()
                            long_running_count += 1
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # 记录清理结果
            total_cleaned = zombie_count + long_running_count
            if total_cleaned > 0:
                logger.warning(f"🧹 清理了 {total_cleaned} 个异常FFmpeg进程 (僵尸: {zombie_count}, 超时: {long_running_count})")
                self.last_cleanup_time = current_time
        
        except Exception as e:
            logger.error(f"清理僵尸进程失败: {e}")
    
    async def check_system_resources(self):
        """检查系统资源使用情况"""
        try:
            # 获取系统资源状态
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk_tmp = psutil.disk_usage('/tmp')
            
            # 统计FFmpeg进程数
            ffmpeg_procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                if proc.info.get('name') and 'ffmpeg' in proc.info['name'].lower():
                    ffmpeg_procs.append(proc)
            
            ffmpeg_count = len(ffmpeg_procs)
            
            # 正常情况：≤14个FFmpeg（信号量限制）
            if ffmpeg_count > 14:
                logger.warning(f"⚠️ FFmpeg进程数较多: {ffmpeg_count} 个 (正常≤14)")
            
            # 异常情况：>16个说明有泄漏
            if ffmpeg_count > 16:
                logger.error(f"🚨 FFmpeg进程数异常: {ffmpeg_count} 个，触发清理")
                await self.cleanup_zombie_processes()
            
            # 记录资源状态（每5分钟记录一次详细信息）
            current_time = time.time()
            if not hasattr(self, '_last_log_time'):
                self._last_log_time = 0
            
            if current_time - self._last_log_time > 300:  # 5分钟
                logger.info(f"📊 系统状态 - CPU: {cpu:.1f}%, 内存: {mem.percent:.1f}%, "
                          f"/tmp: {disk_tmp.percent:.1f}%, FFmpeg进程: {ffmpeg_count}")
                self._last_log_time = current_time
            
            # 警告级别的资源使用
            if cpu > 90:
                logger.warning(f"⚠️ CPU使用率高: {cpu:.1f}%")
            
            if mem.percent > 90:
                logger.warning(f"⚠️ 内存使用率高: {mem.percent:.1f}%")
            
            if disk_tmp.percent > 90:
                logger.error(f"⚠️ /tmp目录空间不足: {disk_tmp.percent:.1f}%")
                await self.cleanup_temp_files()
        
        except Exception as e:
            logger.error(f"检查系统资源失败: {e}")
    
    async def cleanup_temp_files(self):
        """清理/tmp目录中的旧临时文件"""
        try:
            tmp_dir = Path('/tmp')
            cleaned_count = 0
            cleaned_size = 0
            current_time = time.time()
            
            # 清理超过1小时的临时音频/视频文件
            patterns = ['*.mp3', '*.wav', '*.mp4', 'tmp*']
            
            for pattern in patterns:
                for file_path in tmp_dir.glob(pattern):
                    try:
                        # 检查文件修改时间
                        file_mtime = file_path.stat().st_mtime
                        age = current_time - file_mtime
                        
                        # 超过1小时的文件删除
                        if age > 3600:  # 1小时
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            cleaned_count += 1
                            cleaned_size += file_size
                    except (FileNotFoundError, PermissionError):
                        pass  # 文件已被删除或无权限
                    except Exception as e:
                        logger.debug(f"清理文件失败 {file_path}: {e}")
            
            if cleaned_count > 0:
                size_mb = cleaned_size / (1024 * 1024)
                logger.info(f"🧹 清理了 {cleaned_count} 个临时文件, 释放 {size_mb:.2f} MB空间")
        
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")


# 全局监控实例
_monitor = ProcessMonitor()


async def start_process_monitor():
    """启动进程监控（由main.py在启动时调用）"""
    try:
        await _monitor.start_monitoring()
    except Exception as e:
        logger.error(f"进程监控服务异常退出: {e}")

