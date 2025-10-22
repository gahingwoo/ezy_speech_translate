import psutil
import GPUtil
import threading
import time
from datetime import datetime

class SystemMonitor:
    def __init__(self, update_callback=None, interval=1.0):
        self.update_callback = update_callback
        self.interval = interval
        self.running = False
        self.monitor_thread = None
        
    def start(self):
        """Start monitoring system resources"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
            
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            stats = self.get_system_stats()
            if self.update_callback:
                self.update_callback(stats)
            time.sleep(self.interval)
            
    def get_system_stats(self):
        """Get current system statistics"""
        # CPU Usage
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_freq = psutil.cpu_freq()
        
        # Memory Usage
        memory = psutil.virtual_memory()
        memory_used = memory.used / (1024 ** 3)  # Convert to GB
        memory_total = memory.total / (1024 ** 3)
        
        # GPU Stats
        gpu_stats = []
        try:
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                gpu_stats.append({
                    'id': gpu.id,
                    'name': gpu.name,
                    'load': gpu.load * 100,
                    'memory_used': gpu.memoryUsed,
                    'memory_total': gpu.memoryTotal,
                    'temperature': gpu.temperature
                })
        except Exception:
            pass
            
        return {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'cpu': {
                'percent': cpu_percent,
                'freq_current': cpu_freq.current if cpu_freq else 0,
                'freq_max': cpu_freq.max if cpu_freq else 0
            },
            'memory': {
                'used': round(memory_used, 2),
                'total': round(memory_total, 2),
                'percent': memory.percent
            },
            'gpu': gpu_stats
        }