"""
Health monitoring and metrics collection
"""
import asyncio
import time
import psutil
from typing import Dict, Any
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge, Info
from loguru import logger

# Prometheus metrics
request_count = Counter('avatar_requests_total', 'Total number of requests')
request_duration = Histogram('avatar_request_duration_seconds', 'Request duration')
active_sessions = Gauge('avatar_active_sessions', 'Number of active sessions')
memory_usage = Gauge('avatar_memory_usage_mb', 'Memory usage in MB')
cpu_usage = Gauge('avatar_cpu_usage_percent', 'CPU usage percentage')
error_count = Counter('avatar_errors_total', 'Total number of errors', ['error_type'])
model_info = Info('avatar_model_info', 'Information about loaded models')

# Handler-specific metrics
vad_processing_time = Histogram('avatar_vad_processing_seconds', 'VAD processing time')
asr_processing_time = Histogram('avatar_asr_processing_seconds', 'ASR processing time')
llm_processing_time = Histogram('avatar_llm_processing_seconds', 'LLM processing time')
tts_processing_time = Histogram('avatar_tts_processing_seconds', 'TTS processing time')
avatar_processing_time = Histogram('avatar_generation_processing_seconds', 'Avatar generation time')


class HealthMonitor:
    """System health monitoring"""
    
    def __init__(self):
        self.start_time = time.time()
        self.is_running = False
        self._last_check = datetime.now()
        self._health_status = {
            "status": "healthy",
            "issues": []
        }
    
    async def start(self):
        """Start health monitoring"""
        self.is_running = True
        logger.info("Health monitor started")
        
        while self.is_running:
            try:
                await self._check_health()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                error_count.labels(error_type="health_check").inc()
    
    async def _check_health(self):
        """Perform health checks"""
        issues = []
        
        # Check CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_usage.set(cpu_percent)
        if cpu_percent > 90:
            issues.append({
                "type": "high_cpu",
                "message": f"CPU usage is high: {cpu_percent}%",
                "severity": "warning"
            })
        
        # Check memory usage
        memory = psutil.virtual_memory()
        memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
        memory_usage.set(memory_mb)
        
        if memory.percent > 85:
            issues.append({
                "type": "high_memory",
                "message": f"Memory usage is high: {memory.percent}%",
                "severity": "warning"
            })
        
        # Check disk space
        disk = psutil.disk_usage('/')
        if disk.percent > 90:
            issues.append({
                "type": "low_disk_space",
                "message": f"Disk usage is high: {disk.percent}%",
                "severity": "warning"
            })
        
        # Update health status
        self._health_status = {
            "status": "healthy" if not issues else "degraded",
            "issues": issues,
            "last_check": datetime.now().isoformat()
        }
        
        self._last_check = datetime.now()
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        uptime = time.time() - self.start_time
        
        return {
            "status": self._health_status["status"],
            "uptime_seconds": uptime,
            "issues": self._health_status["issues"],
            "last_check": self._last_check.isoformat(),
            "system_info": {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(),
                "memory_total_mb": psutil.virtual_memory().total / 1024 / 1024,
                "memory_available_mb": psutil.virtual_memory().available / 1024 / 1024,
                "memory_percent": psutil.virtual_memory().percent,
                "disk_total_gb": psutil.disk_usage('/').total / 1024 / 1024 / 1024,
                "disk_free_gb": psutil.disk_usage('/').free / 1024 / 1024 / 1024,
                "disk_percent": psutil.disk_usage('/').percent
            }
        }
    
    def record_request(self):
        """Record a new request"""
        request_count.inc()
    
    def record_error(self, error_type: str):
        """Record an error"""
        error_count.labels(error_type=error_type).inc()
    
    def update_active_sessions(self, count: int):
        """Update active sessions count"""
        active_sessions.set(count)
    
    def stop(self):
        """Stop health monitoring"""
        self.is_running = False
        logger.info("Health monitor stopped")


# Context managers for timing
class timer:
    """Context manager for timing operations"""
    
    def __init__(self, metric: Histogram):
        self.metric = metric
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.metric.observe(duration)
