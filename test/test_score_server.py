"""测试 score_server.py 的 ScoreHandler 各端点"""

import json
import io
from pathlib import Path

import pytest

import score_server


class MockSocket:
    """模拟 wfile 用于捕获响应"""
    def __init__(self):
        self._buf = io.BytesIO()

    def write(self, data):
        self._buf.write(data)

    def getvalue(self):
        return self._buf.getvalue()


def make_handler(tmp_path, monkeypatch):
    """创建测试用的 ScoreHandler，重定向路径到 tmp_path"""
    monkeypatch.setattr(score_server, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(score_server, "LATEST_FILE", tmp_path / "latest.json")
    monkeypatch.setattr(score_server, "HTML_FILE", Path(__file__).parent.parent / "score.html")
    monkeypatch.setattr(score_server, "SUMMARY_FILE", Path(__file__).parent.parent / "summary.html")

    # 构造 handler
    handler = score_server.ScoreHandler.__new__(score_server.ScoreHandler)
    handler.wfile = MockSocket()
    handler.rfile = io.BytesIO()
    # mock HTTP 响应方法
    handler._sent_status = None
    handler._sent_headers = {}

    def mock_send_response(status):
        handler._sent_status = status

    def mock_send_header(key, val):
        handler._sent_headers[key] = val

    def mock_end_headers():
        pass

    handler.send_response = mock_send_response
    handler.send_header = mock_send_header
    handler.end_headers = mock_end_headers

    def _json_response(data, status=200):
        # 绕过 send_response，直接捕获 JSON
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        handler._sent_status = status
        handler._response_body = body.decode("utf-8")
        handler.wfile.write(body)

    handler._json_response = lambda data, status=200: _json_response(data, status)

    return handler


@pytest.fixture
def handler(tmp_path, monkeypatch):
    return make_handler(tmp_path, monkeypatch)


class TestListFiles:
    """_list_files 测试"""

    def test_returns_latest_json_if_exists(self, handler, tmp_path):
        (tmp_path / "latest.json").write_text("{}")
        files = handler._list_files()
        assert "latest.json" in files

    def test_returns_run_files(self, handler, tmp_path):
        (tmp_path / "run_20260101_000000.json").write_text("{}")
        (tmp_path / "run_20260102_000000.json").write_text("{}")
        files = handler._list_files()
        run_files = [f for f in files if f.startswith("run_")]
        assert len(run_files) == 2

    def test_returns_claude_code_files(self, handler, tmp_path):
        (tmp_path / "claude_code_20260101_000000.json").write_text("{}")
        files = handler._list_files()
        cc = [f for f in files if f.startswith("claude_code_")]
        assert len(cc) == 1

    def test_returns_codex_files(self, handler, tmp_path):
        (tmp_path / "codex_20260101_000000.json").write_text("{}")
        files = handler._list_files()
        cx = [f for f in files if f.startswith("codex_")]
        assert len(cx) == 1


class TestLoadFile:
    """_load_file 测试"""

    def test_missing_file_returns_404(self, handler):
        handler._json_response = lambda d, s=200: setattr(handler, "_resp", (d, s))
        handler._load_file("nonexistent.json")
        assert handler._resp[1] == 404

    def test_missing_filename_returns_400(self, handler):
        handler._json_response = lambda d, s=200: setattr(handler, "_resp", (d, s))
        handler._load_file(None)
        assert handler._resp[1] == 400

    def test_load_new_format_includes_skipped(self, handler, tmp_path):
        data = {"records": [{"a": 1}], "skipped": ["model-x"]}
        (tmp_path / "test.json").write_text(json.dumps(data), encoding="utf-8")

        handler._json_response = lambda d, s=200: setattr(handler, "_resp", d)
        handler._load_file("test.json")
        result = handler._resp
        # _skipped 附加在列表末尾
        assert any(isinstance(r, dict) and "_skipped" in r for r in result)
        skipped_item = next(r for r in result if isinstance(r, dict) and "_skipped" in r)
        assert skipped_item["_skipped"] == ["model-x"]

    def test_load_old_format_list(self, handler, tmp_path):
        data = [{"a": 1}, {"b": 2}]
        (tmp_path / "test.json").write_text(json.dumps(data), encoding="utf-8")

        handler._json_response = lambda d, s=200: setattr(handler, "_resp", d)
        handler._load_file("test.json")
        assert handler._resp == data


class TestSaveFile:
    """_save_file 测试"""

    def test_save_preserves_format(self, handler, tmp_path):
        # 创建原文件
        original = {"records": [{"prompt_id": "p1"}], "skipped": ["m1"]}
        (tmp_path / "test.json").write_text(json.dumps(original), encoding="utf-8")

        # 模拟保存请求
        handler.headers = {"Content-Length": "0"}
        handler.rfile = io.BytesIO(
            json.dumps([{"prompt_id": "p1", "quality_score": 5}]).encode("utf-8")
        )

        saved = handler._save_file("test.json")
        assert saved is None  # 调用 _json_response 而非 return

    def test_save_preserves_skipped_from_original(self, handler, tmp_path):
        original = {"records": [{"prompt_id": "p1"}], "skipped": ["m1", "m2"]}
        (tmp_path / "test.json").write_text(json.dumps(original), encoding="utf-8")

        body = json.dumps([{"prompt_id": "p1", "quality_score": 3}]).encode("utf-8")
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)

        handler._save_file("test.json")

        saved = json.loads((tmp_path / "test.json").read_text(encoding="utf-8"))
        assert saved["skipped"] == ["m1", "m2"]
        assert saved["records"][0]["quality_score"] == 3

    def test_save_with_new_skipped_overrides(self, handler, tmp_path):
        original = {"records": [{"prompt_id": "p1"}], "skipped": ["old"]}
        (tmp_path / "test.json").write_text(json.dumps(original), encoding="utf-8")

        body = json.dumps([
            {"prompt_id": "p1"},
            {"_skipped": ["new_skip"]},
        ]).encode("utf-8")
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)

        handler._save_file("test.json")

        saved = json.loads((tmp_path / "test.json").read_text(encoding="utf-8"))
        assert saved["skipped"] == ["new_skip"]


class TestSummary:
    """_summary 测试"""

    def test_aggregates_multiple_files(self, handler, tmp_path):
        (tmp_path / "run_001.json").write_text(json.dumps({
            "records": [{"model": "m1", "scene": "s1", "latency_s": 1.0, "error": None,
                         "quality_score": 4, "tokens_input": 10, "tokens_output": 20,
                         "cost_usd": 0.001, "usability": "直接用"}],
            "skipped": ["x"],
        }), encoding="utf-8")
        (tmp_path / "run_002.json").write_text(json.dumps({
            "records": [{"model": "m1", "scene": "s2", "latency_s": 2.0, "error": None,
                         "quality_score": 5, "tokens_input": 30, "tokens_output": 40,
                         "cost_usd": 0.002, "usability": "直接用"}],
            "skipped": ["y"],
        }), encoding="utf-8")

        summary = handler._summary()
        assert len(summary["models"]) >= 1
        assert summary["total_files"] == 2
        assert "x" in summary["skipped"]
        assert "y" in summary["skipped"]

    def test_includes_claude_code_and_codex(self, handler, tmp_path):
        (tmp_path / "claude_code_001.json").write_text(json.dumps({
            "records": [{"model": "claude-code", "scene": "s1", "latency_s": 5.0,
                         "error": None, "quality_score": None, "tokens_input": 0,
                         "tokens_output": 0, "cost_usd": 0}],
        }), encoding="utf-8")
        (tmp_path / "codex_001.json").write_text(json.dumps({
            "records": [{"model": "codex", "scene": "s1", "latency_s": 3.0,
                         "error": None, "quality_score": None, "tokens_input": 0,
                         "tokens_output": 0, "cost_usd": 0}],
        }), encoding="utf-8")

        summary = handler._summary()
        model_names = [m["model"] for m in summary["models"]]
        assert "claude-code" in model_names
        assert "codex" in model_names
        assert summary["total_files"] == 2

    def test_compatible_with_old_list_format(self, handler, tmp_path):
        (tmp_path / "run_old.json").write_text(json.dumps([
            {"model": "old_model", "scene": "s1", "latency_s": 1.0, "error": None,
             "quality_score": 3, "tokens_input": 5, "tokens_output": 10,
             "cost_usd": 0.001},
        ]), encoding="utf-8")

        summary = handler._summary()
        assert any(m["model"] == "old_model" for m in summary["models"])


class TestGetPrompts:
    """_get_prompts 测试"""

    def test_returns_prompts_json(self, handler):
        prompts = handler._get_prompts()
        assert isinstance(prompts, list)
        assert len(prompts) > 0
        assert "id" in prompts[0]
        assert "prompt" in prompts[0]
