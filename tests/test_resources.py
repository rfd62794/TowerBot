"""Tests for system resources monitoring."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


@test("resources: get_system_resources returns RAM, disk, CPU metrics")
def test_get_system_resources():
    from unittest.mock import patch, MagicMock
    from tools.meta.resources import ResourceTools
    
    # Mock psutil
    mock_ram = MagicMock()
    mock_ram.total = 16 * (1024**3)
    mock_ram.used = 8 * (1024**3)
    mock_ram.available = 8 * (1024**3)
    mock_ram.percent = 50.0
    
    mock_disk = MagicMock()
    mock_disk.total = 500 * (1024**3)
    mock_disk.used = 200 * (1024**3)
    mock_disk.free = 300 * (1024**3)
    mock_disk.percent = 40.0
    
    with patch('psutil.virtual_memory', return_value=mock_ram), \
         patch('psutil.disk_usage', return_value=mock_disk), \
         patch('psutil.cpu_percent', return_value=25.0):
        
        tools = ResourceTools()
        result = tools.get_system_resources()
        
        assert result["ok"] is True, f"Expected ok=True, got {result}"
        assert result["ram_total_gb"] == 16.0, f"Expected 16.0GB, got {result['ram_total_gb']}"
        assert result["ram_available_gb"] == 8.0, f"Expected 8.0GB, got {result['ram_available_gb']}"
        assert result["disk_free_gb"] == 300.0, f"Expected 300.0GB, got {result['disk_free_gb']}"
        assert result["cpu_percent"] == 25.0, f"Expected 25.0%, got {result['cpu_percent']}"


@test("resources: get_ollama_loaded returns model and RAM usage")
def test_get_ollama_loaded():
    from unittest.mock import patch, MagicMock
    from tools.meta.resources import ResourceTools
    
    # Mock Ollama API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"model": "gemma3:4b", "vm_rss": 3 * (1024**3)}
    mock_response.raise_for_status = MagicMock()
    
    with patch('requests.get', return_value=mock_response):
        tools = ResourceTools()
        result = tools.get_ollama_loaded()
        
        assert result["ok"] is True, f"Expected ok=True, got {result}"
        assert result["model"] == "gemma3:4b", f"Expected gemma3:4b, got {result['model']}"
        assert result["ram_used_gb"] == 3.0, f"Expected 3.0GB, got {result['ram_used_gb']}"


@test("resources: get_ollama_model_sizes returns installed models")
def test_get_ollama_model_sizes():
    from unittest.mock import patch, MagicMock
    from tools.meta.resources import ResourceTools
    
    # Mock Ollama API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [
            {"name": "gemma3:4b", "size": 3 * (1024**3), "modified_at": "2024-01-01"},
            {"name": "qwen2.5:7b", "size": 5 * (1024**3), "modified_at": "2024-01-02"}
        ]
    }
    mock_response.raise_for_status = MagicMock()
    
    with patch('requests.get', return_value=mock_response):
        tools = ResourceTools()
        result = tools.get_ollama_model_sizes()
        
        assert result["ok"] is True, f"Expected ok=True, got {result}"
        assert result["count"] == 2, f"Expected 2 models, got {result['count']}"
        assert len(result["models"]) == 2, f"Expected 2 models, got {len(result['models'])}"
        assert result["models"][0]["name"] == "gemma3:4b"
        assert result["models"][0]["size_gb"] == 3.0


@test("resources: get_privybot_memory returns process RAM usage")
def test_get_privybot_memory():
    from unittest.mock import patch, MagicMock
    from tools.meta.resources import ResourceTools
    
    # Mock psutil Process
    mock_mem_info = MagicMock()
    mock_mem_info.rss = 500 * (1024**2)  # 500MB
    mock_mem_info.vms = 1000 * (1024**2)  # 1GB
    
    with patch('psutil.Process') as mock_process:
        mock_process.return_value.memory_info.return_value = mock_mem_info
        
        tools = ResourceTools()
        result = tools.get_privybot_memory()
        
        assert result["ok"] is True, f"Expected ok=True, got {result}"
        assert result["rss_mb"] == 500.0, f"Expected 500MB, got {result['rss_mb']}"
        assert result["vms_mb"] == 1000.0, f"Expected 1000MB, got {result['vms_mb']}"


if __name__ == "__main__":
    passed, total = run_all()
    print(f"\n{passed}/{total} passed")
    sys.exit(0 if passed == total else 1)
