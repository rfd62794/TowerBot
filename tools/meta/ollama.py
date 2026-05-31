"""Ollama tools — local model health and management."""

from api._handler import BaseTool
from api.local.ollama_api import ollama_api


class OllamaTools(BaseTool):
    def check_ollama_health(self) -> dict:
        """Check if Ollama service is running and responsive."""
        try:
            result = ollama_api.list_models()
            if "error" in result:
                return self.error(result["error"])
            
            models = result.get("models", [])
            return self.success({
                "status": "healthy",
                "model_count": len(models),
                "models": [m["name"] for m in models]
            })
        except Exception as e:
            return self.error(f"Ollama health check failed: {str(e)}")
    
    def list_local_models(self) -> dict:
        """List all available local Ollama models."""
        result = ollama_api.list_models()
        
        if "error" in result:
            return self.error(result["error"])
        
        models = result.get("models", [])
        formatted = []
        for model in models:
            formatted.append({
                "name": model.get("name"),
                "size_gb": round(model.get("size", 0) / (1024**3), 2),
                "modified_at": model.get("modified_at")
            })
        
        return self.success({
            "count": len(formatted),
            "models": formatted
        })
    
    def pull_ollama_model(self, model: str) -> dict:
        """
        Pull a model from Ollama registry.
        
        Args:
            model: Model name to pull (e.g., "gemma3:4b")
        """
        result = ollama_api.pull_model(model)
        
        if "error" in result:
            return self.error(result["error"])
        
        return self.success({
            "status": "pulled",
            "model": model
        })
