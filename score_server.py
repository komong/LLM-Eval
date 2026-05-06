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

ALL_MODELS = ["deepseek-v4-flash", "deepseek-v4-flash-think", "deepseek-v4-pro", "minimax", "claude-sonnet"]
LATEST_FILE = RESULTS_DIR / "latest.json"


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
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/save":
            params = parse_qs(parsed.query)
            filename = params.get("file", [None])[0]
            self._save_file(filename)
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

    def _list_files(self):
        files = []
        if LATEST_FILE.exists():
            files.append("latest.json")
        files += sorted(
            [f.name for f in RESULTS_DIR.glob("run_*.json")],
            reverse=True,
        )
        return files

    def _summary(self):
        """聚合所有 run_*.json，返回按模型+场景的汇总数据"""
        all_records = []
        all_skipped = set()
        for f in sorted(RESULTS_DIR.glob("run_*.json")):
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
            })

        return {
            "total_files": len([f for f in RESULTS_DIR.glob("run_*.json")]),
            "models": models_summary,
            "scene_matrix": scene_matrix,
            "skipped": sorted(all_skipped),
            "all_models": ALL_MODELS,
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
                result = data["records"]
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
