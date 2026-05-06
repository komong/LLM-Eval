#!/usr/bin/env python3
"""
评分服务器 - 提供 HTTP API + HTML 评分页面
用法:
  python score_server.py                        # 默认端口 8765
  python score_server.py --port 9999            # 指定端口
  python score_server.py --file results/run_xxx.json  # 直接打开指定文件
"""

import json
import argparse
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

RESULTS_DIR = Path(__file__).parent / "results"
HTML_FILE = Path(__file__).parent / "score.html"
SUMMARY_FILE = Path(__file__).parent / "summary.html"

ALL_MODELS = ["deepseek-v4-flash", "deepseek-v4-flash-think", "deepseek-v4-pro", "minimax", "minimax-m2.7", "claude-sonnet"]
LATEST_FILE = RESULTS_DIR / "latest.json"
MODELS_CONFIG_FILE = Path(__file__).parent / "models_config.json"
BILLING_CONFIG_FILE = Path(__file__).parent / "billing_config.json"

MODELS_DETAIL = {
    "deepseek-v4-flash": {"provider": "deepseek", "model_id": "deepseek-v4-flash", "price_input": 1.0, "price_output": 2.0, "thinking": False},
    "deepseek-v4-flash-think": {"provider": "deepseek", "model_id": "deepseek-v4-flash", "price_input": 1.0, "price_output": 2.0, "thinking": True},
    "deepseek-v4-pro": {"provider": "deepseek", "model_id": "deepseek-v4-pro", "price_input": 3.0, "price_output": 6.0, "thinking": False},
    "minimax": {"provider": "minimax", "model_id": "MiniMax-M2.5-highspeed", "price_input": 0.20, "price_output": 0.55, "is_token_plan": True},
    "minimax-m2.7": {"provider": "minimax", "model_id": "MiniMax-M2.7", "price_input": 0.20, "price_output": 0.55, "is_token_plan": True},
    "claude-sonnet": {"provider": "anthropic", "model_id": "claude-sonnet-4-5", "price_input": 3.00, "price_output": 15.00},
}

DEFAULT_BILLING = {"display_currency": "USD", "exchange_rate": 7.25, "exclude_token_plan": False}


class ScoreHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/files":
            self._json_response(self._list_files())
        elif parsed.path == "/api/load":
            params = parse_qs(parsed.query)
            filename = params.get("file", [None])[0]
            self._load_file(filename)
        elif parsed.path == "/api/summary":
            self._json_response(self._summary())
        elif parsed.path == "/" or parsed.path == "/score.html":
            self._serve_html()
        elif parsed.path == "/summary.html":
            self._serve_summary()
        elif parsed.path == "/models.html":
            self._serve_page("models.html")
        elif parsed.path == "/billing.html":
            self._serve_page("billing.html")
        elif parsed.path == "/api/models":
            self._json_response(self._get_models_config())
        elif parsed.path == "/api/prompts":
            self._json_response(self._get_prompts())
        elif parsed.path == "/api/billing-config":
            self._json_response(self._get_billing_config())
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/save":
            params = parse_qs(parsed.query)
            filename = params.get("file", [None])[0]
            self._save_file(filename)
        elif parsed.path == "/api/models":
            self._save_models_config()
        elif parsed.path == "/api/billing-config":
            self._save_billing_config()
        else:
            self.send_error(404)

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self):
        if HTML_FILE.exists():
            content = HTML_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "score.html not found")

    def _serve_summary(self):
        if SUMMARY_FILE.exists():
            content = SUMMARY_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "summary.html not found")

    def _serve_page(self, filename):
        page_path = Path(__file__).parent / filename
        if page_path.exists():
            content = page_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, f"{filename} not found")

    def _get_models_config(self):
        """返回所有模型配置（含 models_config.json 覆盖的 enabled 状态）"""
        overrides = {}
        if MODELS_CONFIG_FILE.exists():
            try:
                overrides = json.loads(MODELS_CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        result = {}
        for name in ALL_MODELS:
            detail = dict(MODELS_DETAIL.get(name, {}))
            detail["enabled"] = overrides.get(name, detail.get("enabled", True))
            result[name] = detail
        return result

    def _get_prompts(self):
        """返回 prompts.json 内容"""
        prompts_path = Path(__file__).parent / "prompts.json"
        if prompts_path.exists():
            return json.loads(prompts_path.read_text(encoding="utf-8"))
        return []

    def _save_models_config(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            config = json.loads(body)
            MODELS_CONFIG_FILE.write_text(
                json.dumps(config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._json_response({"ok": True})
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _get_billing_config(self):
        """读取计费配置"""
        if BILLING_CONFIG_FILE.exists():
            try:
                return json.loads(BILLING_CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return dict(DEFAULT_BILLING)

    def _save_billing_config(self):
        """保存计费配置"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            config = json.loads(body)
            # 校验字段
            cleaned = {}
            if "display_currency" in config and config["display_currency"] in ("USD", "RMB"):
                cleaned["display_currency"] = config["display_currency"]
            else:
                cleaned["display_currency"] = DEFAULT_BILLING["display_currency"]
            cleaned["exchange_rate"] = float(config.get("exchange_rate", DEFAULT_BILLING["exchange_rate"]))
            cleaned["exclude_token_plan"] = bool(config.get("exclude_token_plan", DEFAULT_BILLING["exclude_token_plan"]))
            BILLING_CONFIG_FILE.write_text(
                json.dumps(cleaned, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._json_response({"ok": True, "config": cleaned})
        except (ValueError, TypeError):
            self._json_response({"error": "汇率必须为有效数字"}, 400)
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _list_files(self):
        files = []
        if LATEST_FILE.exists():
            files.append("latest.json")
        for pat in ("run_*.json", "claude_code_*.json", "codex_*.json"):
            files += sorted(
                [f.name for f in RESULTS_DIR.glob(pat)],
                reverse=True,
            )
        return files

    def _summary(self):
        """聚合所有结果文件，返回按模型+场景的汇总数据"""
        billing = self._get_billing_config()
        exclude_tp = billing.get("exclude_token_plan", False)

        all_records = []
        all_skipped = set()
        for pat in ("run_*.json", "claude_code_*.json", "codex_*.json"):
            for f in sorted(RESULTS_DIR.glob(pat)):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and "records" in data:
                        all_records.extend(data["records"])
                        all_skipped.update(data.get("skipped", []))
                    elif isinstance(data, list):
                        # 兼容旧格式
                        all_records.extend(data)
                except Exception:
                    pass

        # 按模型分组
        by_model = {}
        for r in all_records:
            m = r["model"]
            if m not in by_model:
                by_model[m] = []
            by_model[m].append(r)

        models_summary = []
        for model, records in sorted(by_model.items()):
            success = [r for r in records if not r.get("error")]
            scored = [r for r in success if r.get("quality_score")]
            latencies = [r["latency_s"] for r in success if r.get("latency_s")]
            total_input = sum(r.get("tokens_input", 0) for r in success)
            total_output = sum(r.get("tokens_output", 0) for r in success)
            total_cost = sum(r.get("cost_usd", 0) for r in success)
            usability_dist = {}
            for r in scored:
                u = r.get("usability", "未知")
                usability_dist[u] = usability_dist.get(u, 0) + 1

            is_tp = success[0].get("is_token_plan", False) if success else False
            models_summary.append({
                "model": model,
                "total_runs": len(records),
                "success": len(success),
                "scored": len(scored),
                "avg_quality": round(sum(r["quality_score"] for r in scored) / len(scored), 1) if scored else None,
                "avg_latency": round(sum(latencies) / len(latencies), 1) if latencies else None,
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_tokens": total_input + total_output,
                "total_cost": round(total_cost, 5),
                "usability_dist": usability_dist,
                "is_token_plan": is_tp,
            })

        # 按 模型+场景 分组
        by_model_scene = {}
        for r in all_records:
            key = f"{r['model']}|{r['scene']}"
            if key not in by_model_scene:
                by_model_scene[key] = []
            by_model_scene[key].append(r)

        scene_matrix = []
        for key, records in sorted(by_model_scene.items()):
            model, scene = key.split("|", 1)
            success = [r for r in records if not r.get("error")]
            scored = [r for r in success if r.get("quality_score")]
            latencies = [r["latency_s"] for r in success if r.get("latency_s")]
            total_input = sum(r.get("tokens_input", 0) for r in success)
            total_output = sum(r.get("tokens_output", 0) for r in success)
            total_cost = sum(r.get("cost_usd", 0) for r in success)

            scene_matrix.append({
                "model": model,
                "scene": scene,
                "runs": len(records),
                "success": len(success),
                "scored": len(scored),
                "avg_quality": round(sum(r["quality_score"] for r in scored) / len(scored), 1) if scored else None,
                "avg_latency": round(sum(latencies) / len(latencies), 1) if latencies else None,
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_tokens": total_input + total_output,
                "total_cost": round(total_cost, 5),
                "is_token_plan": success[0].get("is_token_plan", False) if success else False,
            })

        return {
            "total_files": sum(1 for pat in ("run_*.json", "claude_code_*.json", "codex_*.json") for _ in RESULTS_DIR.glob(pat)),
            "models": models_summary,
            "scene_matrix": scene_matrix,
            "skipped": sorted(all_skipped),
            "all_models": ALL_MODELS,
            "billing": billing,
        }

    def _load_file(self, filename):
        if not filename:
            return self._json_response({"error": "缺少 file 参数"}, 400)

        file_path = RESULTS_DIR / filename
        if not file_path.exists():
            return self._json_response({"error": "文件不存在"}, 404)

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            # 兼容新旧格式
            if isinstance(data, dict) and "records" in data:
                # 新格式: {"records": [...], "skipped": [...]}
                result = list(data["records"])
                result.append({"_skipped": data.get("skipped", [])})
                self._json_response(result)
            else:
                self._json_response(data)
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _save_file(self, filename):
        if not filename:
            return self._json_response({"error": "缺少 file 参数"}, 400)

        file_path = RESULTS_DIR / filename
        if not file_path.exists():
            return self._json_response({"error": "文件不存在"}, 404)

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            new_records = json.loads(body)

            # 分离 _skipped 标记
            skipped = []
            records = []
            for r in new_records:
                if isinstance(r, dict) and "_skipped" in r:
                    skipped = r["_skipped"]
                else:
                    records.append(r)

            # 保留原文件的 skipped（如果没有新的）
            if not skipped:
                old = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(old, dict):
                    skipped = old.get("skipped", [])

            file_path.write_text(
                json.dumps({"records": records, "skipped": skipped}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._json_response({"ok": True, "file": filename})
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def log_message(self, format, *args):
        # 精简日志
        pass


def main():
    parser = argparse.ArgumentParser(description="LLM Benchmark 评分服务器")
    parser.add_argument("--port", type=int, default=8765, help="端口号 (默认 8765)")
    parser.add_argument("--file", help="直接加载的结果文件")
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), ScoreHandler)
    url = f"http://127.0.0.1:{args.port}"
    if args.file:
        url += f"?file={args.file}"
    elif LATEST_FILE.exists():
        url += "?file=latest.json"

    print(f"评分页面: {url}")
    webbrowser.open(url)
    print(f"按 Ctrl+C 停止服务")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
