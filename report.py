#!/usr/bin/env python3
"""
LLM Benchmark Report
用法:
  python report.py --file results/run_20260506_120000.json   # 查看指定结果
  python report.py --file results/run_xxx.json --score       # 进入评分模式
  python report.py --compare                                  # 汇总所有结果对比
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

RESULTS_DIR = Path(__file__).parent / "results"

USABILITY_OPTIONS = {
    "1": "直接用",
    "2": "小改后用",
    "3": "大改后用",
    "4": "重写",
}


# ── 评分模式 ──────────────────────────────────────────
def score_results(file_path: Path):
    data = json.loads(file_path.read_text(encoding="utf-8"))
    # 按 prompt 分组
    prompts = {}
    for r in data:
        pid = r["prompt_id"]
        if pid not in prompts:
            prompts[pid] = []
        prompts[pid].append(r)

    for pid, records in prompts.items():
        print(f"\n{'='*60}")
        print(f"场景: {records[0]['scene']} | ID: {pid}")
        print(f"需求: {records[0].get('prompt_preview', '')}")
        print(f"{'='*60}")

        for r in records:
            if r.get("quality_score") is not None:
                print(f"  {r['model']}: 已评分，跳过")
                continue
            if r.get("error"):
                print(f"  {r['model']}: 调用失败，跳过")
                continue

            print(f"\n── {r['model']} ──")
            print(f"耗时: {r['latency_s']}s | token: {r['tokens_input']}+{r['tokens_output']} | 费用: ${r['cost_usd']:.5f}")
            print(f"\n输出:\n{r['output'][:800]}{'...' if len(r['output']) > 800 else ''}\n")

            # 评分
            score = None
            while score not in [str(i) for i in range(1, 6)]:
                score = input("质量评分 (1-5，5最好): ").strip()

            usability = None
            while usability not in USABILITY_OPTIONS:
                print("可用度: " + " | ".join(f"{k}.{v}" for k, v in USABILITY_OPTIONS.items()))
                usability = input("选择: ").strip()

            notes = input("备注 (回车跳过): ").strip()

            r["quality_score"] = int(score)
            r["usability"] = USABILITY_OPTIONS[usability]
            r["notes"] = notes if notes else None

    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ 评分已保存到 {file_path}")


# ── 单次报告 ──────────────────────────────────────────
def show_report(file_path: Path):
    data = json.loads(file_path.read_text(encoding="utf-8"))

    print(f"\n{'='*60}")
    print(f"测试报告: {file_path.name}")
    print(f"{'='*60}")

    # 按模型汇总
    by_model = {}
    for r in data:
        m = r["model"]
        if m not in by_model:
            by_model[m] = {"records": [], "total_cost": 0, "total_latency": []}
        by_model[m]["records"].append(r)
        by_model[m]["total_cost"] += r.get("cost_usd", 0)
        if r.get("latency_s"):
            by_model[m]["total_latency"].append(r["latency_s"])

    print(f"\n{'模型':<20} {'平均耗时':>8} {'总费用':>10} {'平均质量':>8} {'成功率':>6}")
    print("-" * 60)

    for model, stats in by_model.items():
        records = stats["records"]
        success = [r for r in records if not r.get("error")]
        avg_latency = sum(stats["total_latency"]) / len(stats["total_latency"]) if stats["total_latency"] else 0
        scored = [r for r in records if r.get("quality_score")]
        avg_quality = sum(r["quality_score"] for r in scored) / len(scored) if scored else "-"
        success_rate = f"{len(success)}/{len(records)}"

        avg_quality_str = f"{avg_quality:.1f}" if isinstance(avg_quality, float) else avg_quality
        print(f"{model:<20} {avg_latency:>7.1f}s {stats['total_cost']:>9.5f}$ {avg_quality_str:>8} {success_rate:>6}")

    # 按场景明细
    print(f"\n\n── 场景明细 ──")
    by_scene = {}
    for r in data:
        s = r["scene"]
        if s not in by_scene:
            by_scene[s] = []
        by_scene[s].append(r)

    for scene, records in by_scene.items():
        print(f"\n【{scene}】")
        print(f"  {'模型':<18} {'耗时':>6} {'费用':>9} {'质量':>5} {'可用度'}")
        print(f"  {'-'*55}")
        for r in sorted(records, key=lambda x: x["model"]):
            if r.get("error"):
                print(f"  {r['model']:<18} {'ERROR':>6}")
                continue
            quality = str(r.get("quality_score", "-"))
            usability = r.get("usability", "-")
            print(f"  {r['model']:<18} {r['latency_s']:>5.1f}s ${r['cost_usd']:>8.5f} {quality:>5} {usability}")


# ── 汇总对比 ──────────────────────────────────────────
def compare_all():
    files = sorted(RESULTS_DIR.glob("run_*.json"))
    if not files:
        print("没有找到测试结果文件")
        return

    all_records = []
    for f in files:
        all_records.extend(json.loads(f.read_text(encoding="utf-8")))

    print(f"\n汇总 {len(files)} 次测试，共 {len(all_records)} 条记录\n")

    by_model_scene = {}
    for r in all_records:
        key = (r["model"], r["scene"])
        if key not in by_model_scene:
            by_model_scene[key] = []
        by_model_scene[key].append(r)

    print(f"{'模型':<18} {'场景':<12} {'次数':>4} {'均耗时':>7} {'均费用':>9} {'均质量':>6}")
    print("-" * 65)

    for (model, scene), records in sorted(by_model_scene.items()):
        success = [r for r in records if not r.get("error")]
        latencies = [r["latency_s"] for r in success if r.get("latency_s")]
        costs = [r["cost_usd"] for r in success]
        scored = [r["quality_score"] for r in success if r.get("quality_score")]

        avg_lat = f"{sum(latencies)/len(latencies):.1f}s" if latencies else "-"
        avg_cost = f"${sum(costs)/len(costs):.5f}" if costs else "-"
        avg_q = f"{sum(scored)/len(scored):.1f}" if scored else "-"

        print(f"{model:<18} {scene:<12} {len(records):>4} {avg_lat:>7} {avg_cost:>9} {avg_q:>6}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="指定结果文件路径")
    parser.add_argument("--score", action="store_true", help="进入评分模式")
    parser.add_argument("--compare", action="store_true", help="汇总所有结果对比")
    args = parser.parse_args()

    if args.compare:
        compare_all()
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"文件不存在: {file_path}")
        elif args.score:
            score_results(file_path)
        else:
            show_report(file_path)
    else:
        # 默认显示最新结果
        files = sorted(RESULTS_DIR.glob("run_*.json"))
        if files:
            show_report(files[-1])
        else:
            print("没有找到结果文件，请先运行 runner.py")
