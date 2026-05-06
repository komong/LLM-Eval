"""共享 fixtures：临时目录、示例数据"""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_dir():
    """创建临时目录，测试结束后自动清理"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_records():
    """一组示例评分记录"""
    return [
        {
            "prompt_id": "frontend_001",
            "scene": "前端开发",
            "complexity": "low",
            "model": "deepseek-v4-flash",
            "provider": "deepseek",
            "timestamp": "2026-05-06T10:40:35",
            "latency_s": 64.09,
            "tokens_input": 27,
            "tokens_output": 4096,
            "cost_usd": 0.008219,
            "output": "<html>...</html>",
            "error": None,
            "quality_score": None,
            "usability": None,
            "notes": None,
        },
        {
            "prompt_id": "frontend_001",
            "scene": "前端开发",
            "complexity": "low",
            "model": "claude-sonnet",
            "provider": "anthropic",
            "timestamp": "2026-05-06T10:42:00",
            "latency_s": 12.3,
            "tokens_input": 150,
            "tokens_output": 800,
            "cost_usd": 0.01245,
            "output": "Here is the code...",
            "error": None,
            "quality_score": 4,
            "usability": "小改后用",
            "notes": "不错",
        },
    ]


@pytest.fixture
def skipped_models():
    return ["deepseek-v4-flash-think"]


@pytest.fixture
def old_format_file(tmp_dir, sample_records):
    """旧列表格式文件"""
    p = tmp_dir / "old_format.json"
    p.write_text(json.dumps(sample_records, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def new_format_file(tmp_dir, sample_records, skipped_models):
    """新字典格式文件"""
    p = tmp_dir / "new_format.json"
    data = {"records": sample_records, "skipped": skipped_models}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
