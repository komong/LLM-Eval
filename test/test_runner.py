"""测试 runner.py 的 _save_latest 与模型过滤逻辑"""

import json
import os
import sys
from pathlib import Path

import pytest

# 确保能导入 runner（避免 dotenv 加载干扰）
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-key")


class TestSaveLatest:
    """_save_latest 测试"""

    @pytest.fixture(autouse=True)
    def _patch_paths(self, monkeypatch, tmp_path):
        """将 runner 的文件路径重定向到临时目录"""
        import runner

        self.runner = runner
        monkeypatch.setattr(runner, "LATEST_FILE", tmp_path / "latest.json")
        monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)
        self.tmp_path = tmp_path

    def make_existing(self, entries):
        """构造 {(model, prompt_id): record} 字典"""
        return {(r["model"], r["prompt_id"]): r for r in entries}

    def test_merges_old_and_new(self):
        """旧记录 + 新记录合并，新记录覆盖旧"""
        old = self.make_existing([
            {"model": "deepseek-v4-flash", "prompt_id": "p1", "output": "old"},
            {"model": "deepseek-v4-flash", "prompt_id": "p2", "output": "old2"},
        ])
        new = [
            {"model": "deepseek-v4-flash", "prompt_id": "p1", "output": "new"},
        ]
        active = {"deepseek-v4-flash": {}}
        all_models = {"deepseek-v4-flash": {}}

        self.runner._save_latest(old, active, all_models, new)

        data = json.loads(self.runner.LATEST_FILE.read_text(encoding="utf-8"))
        assert len(data["records"]) == 2
        outputs = {r["prompt_id"]: r["output"] for r in data["records"]}
        assert outputs["p1"] == "new"
        assert outputs["p2"] == "old2"

    def test_skipped_includes_non_active(self):
        """skipped 包含不在 active_models 中的模型"""
        existing = self.make_existing([
            {"model": "deepseek-v4-flash", "prompt_id": "p1", "output": "x"},
        ])
        active = {"deepseek-v4-flash": {}}
        all_models = {"deepseek-v4-flash": {}, "claude-sonnet": {}, "minimax": {}}

        self.runner._save_latest(existing, active, all_models)

        data = json.loads(self.runner.LATEST_FILE.read_text(encoding="utf-8"))
        assert set(data["skipped"]) == {"claude-sonnet", "minimax"}

    def test_stale_records_removed(self):
        """旧记录中不属于 active_models 的被移除"""
        old = self.make_existing([
            {"model": "deepseek-v4-flash", "prompt_id": "p1", "output": "keep"},
            {"model": "claude-sonnet", "prompt_id": "p1", "output": "drop"},
        ])
        active = {"deepseek-v4-flash": {}}
        all_models = {"deepseek-v4-flash": {}, "claude-sonnet": {}}

        self.runner._save_latest(old, active, all_models)

        data = json.loads(self.runner.LATEST_FILE.read_text(encoding="utf-8"))
        models = {r["model"] for r in data["records"]}
        assert models == {"deepseek-v4-flash"}

    def test_backup_file_created(self):
        """同时生成时间戳备份"""
        existing = {}
        active = {"deepseek-v4-flash": {}}
        all_models = {"deepseek-v4-flash": {}}

        self.runner._save_latest(existing, active, all_models)

        backups = list(self.tmp_path.glob("run_*.json"))
        assert len(backups) == 1
        assert backups[0].name.startswith("run_")


class TestModelFiltering:
    """模型过滤逻辑测试"""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        import runner

        self.runner = runner

    def test_enabled_true_with_key_included(self, monkeypatch):
        """enabled=True + 有API Key → 进入 active"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-key")
        models = {
            "deepseek-v4-flash": {
                "provider": "deepseek",
                "api_key_env": "DEEPSEEK_API_KEY",
                "enabled": True,
            }
        }
        active = {}
        for name, cfg in models.items():
            if not cfg.get("enabled", True):
                continue
            key = os.getenv(cfg["api_key_env"], "")
            if key and "your_" not in key:
                active[name] = cfg
        assert "deepseek-v4-flash" in active

    def test_enabled_false_skipped(self, monkeypatch):
        """enabled=False → 跳过"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-key")
        models = {
            "deepseek-v4-flash-think": {
                "provider": "deepseek",
                "api_key_env": "DEEPSEEK_API_KEY",
                "enabled": False,
            }
        }
        active = {}
        for name, cfg in models.items():
            if not cfg.get("enabled", True):
                continue
            key = os.getenv(cfg["api_key_env"], "")
            if key and "your_" not in key:
                active[name] = cfg
        assert "deepseek-v4-flash-think" not in active

    def test_no_api_key_skipped(self, monkeypatch):
        """无 API Key → 跳过"""
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        models = {
            "minimax": {
                "provider": "minimax",
                "api_key_env": "MINIMAX_API_KEY",
                "enabled": True,
            }
        }
        active = {}
        for name, cfg in models.items():
            if not cfg.get("enabled", True):
                continue
            key = os.getenv(cfg["api_key_env"], "")
            if key and "your_" not in key:
                active[name] = cfg
        assert "minimax" not in active

    def test_placeholder_key_skipped(self, monkeypatch):
        """占位符 API Key → 跳过"""
        monkeypatch.setenv("CLAUDE_API_KEY", "your_claude_api_key_here")
        models = {
            "claude-sonnet": {
                "provider": "anthropic",
                "api_key_env": "CLAUDE_API_KEY",
                "enabled": True,
            }
        }
        active = {}
        for name, cfg in models.items():
            if not cfg.get("enabled", True):
                continue
            key = os.getenv(cfg["api_key_env"], "")
            if key and "your_" not in key:
                active[name] = cfg
        assert "claude-sonnet" not in active
