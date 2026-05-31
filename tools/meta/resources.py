"""System resources monitoring — RAM, disk, CPU, Ollama metrics."""

import os
import psutil
import requests
from api._handler import BaseTool


class ResourceTools(BaseTool):
    def get_system_resources(self) -> dict:
        """Get current system resources snapshot."""
        try:
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage('C:\\')
            cpu = psutil.cpu_percent(interval=0.1)
            
            return self.success({
                "ram_total_gb": round(ram.total / (1024**3), 2),
                "ram_used_gb": round(ram.used / (1024**3), 2),
                "ram_available_gb": round(ram.available / (1024**3), 2),
                "ram_percent": ram.percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "disk_percent": disk.percent,
                "cpu_percent": cpu
            })
        except Exception as e:
            return self.error(f"Failed to get system resources: {str(e)}")
    
    def get_ollama_loaded(self) -> dict:
        """Get currently loaded Ollama model and its RAM usage."""
        try:
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            url = f"{host}/api/ps"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            return self.success({
                "model": data.get("model"),
                "ram_used_gb": round(data.get("vm_rss", 0) / (1024**3), 2),
                "vm_rss_bytes": data.get("vm_rss", 0)
            })
        except Exception as e:
            return self.error(f"Failed to get Ollama loaded model: {str(e)}")
    
    def get_ollama_model_sizes(self) -> dict:
        """Get all installed Ollama models with their disk sizes."""
        try:
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            url = f"{host}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model in data.get("models", []):
                models.append({
                    "name": model.get("name"),
                    "size_gb": round(model.get("size", 0) / (1024**3), 2),
                    "size_bytes": model.get("size", 0),
                    "modified_at": model.get("modified_at")
                })
            
            return self.success({
                "count": len(models),
                "models": models
            })
        except Exception as e:
            return self.error(f"Failed to get Ollama model sizes: {str(e)}")
    
    def get_privybot_memory(self) -> dict:
        """Get PrivyBot process memory usage."""
        try:
            process = psutil.Process()
            mem_info = process.memory_info()
            
            return self.success({
                "rss_mb": round(mem_info.rss / (1024**2), 2),
                "vms_mb": round(mem_info.vms / (1024**2), 2),
                "rss_gb": round(mem_info.rss / (1024**3), 2),
                "vms_gb": round(mem_info.vms / (1024**3), 2)
            })
        except Exception as e:
            return self.error(f"Failed to get PrivyBot memory: {str(e)}")
