#!/usr/bin/env python3
"""
LLM Benchmark Runner
用法:
  python runner.py                        # 跑所有模型 x 所有 prompt
  python runner.py --model deepseek-v4-flash   # 只跑指定模型
  python runner.py --scene 前端开发       # 只跑指定场景
  python runner.py --prompt-id frontend_001  # 只跑指定 prompt
"""

import os
import json
import time
import asyncio
import argparse
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── 模型配置 ──────────────────────────────────────────
MODELS = {
    "deepseek-v4-flash": {
        "provider": "deepseek",
        "api_base": "https://api.deepseek.com/v1",
        "model_id": "deepseek-v4-flash",
        "api_key_env": "DEEPSEEK_API_KEY",
        # RMB per 1M tokens
        "price_input": 1.0,
        "price_output": 2.0,
        "thinking": False,
        "enabled": True,
    },
    "deepseek-v4-flash-think": {
        "provider": "deepseek",
        "api_base": "https://api.deepseek.com/v1",
        "model_id": "deepseek-v4-flash",
        "api_key_env": "DEEPSEEK_API_KEY",
        "price_input": 1.0,
        "price_output": 2.0,
        "thinking": True,
        "enabled": False,
    },
    "deepseek-v4-pro": {
        "provider": "deepseek",
        "api_base": "https://api.deepseek.com/v1",
        "model_id": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        # 2.5折优惠价 (RMB per 1M tokens)
        "price_input": 3.0,
        "price_output": 6.0,
        "thinking": False,
        "enabled": True,
    },
    "minimax": {
        "provider": "minimax",
        "api_base": "https://api.minimax.chat/v1",
        "model_id": "MiniMax-M2.5-highspeed",
        "api_key_env": "MINIMAX_API_KEY",
        # Token Plan 价格 (USD per 1M tokens)
        "price_input": 0.20,
        "price_output": 0.55,
        "is_token_plan": True,
        "enabled": True,
    },
    "minimax-m2.7": {
        "provider": "minimax",
        "api_base": "https://api.minimax.chat/v1",
        "model_id": "MiniMax-M2.7",
        "api_key_env": "MINIMAX_API_KEY",
        # Token Plan 价格 (USD per 1M tokens)
        "price_input": 0.20,
        "price_output": 0.55,
        "is_token_plan": True,
        "enabled": True,
    },
    "claude-sonnet": {
        "provider": "anthropic",
        "api_base": "https://api.anthropic.com/v1",
        "model_id": "claude-sonnet-4-5",
        "api_key_env": "CLAUDE_API_KEY",
        "price_input": 3.00,
        "price_output": 15.00,
        "enabled": True,
    },
}

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)
LATEST_FILE = RESULTS_DIR / "latest.json"
MODELS_CONFIG_FILE = Path(__file__).parent / "models_config.json"


# ── API 调用 ──────────────────────────────────────────
async def call_deepseek(model_cfg: dict, prompt: str, client: httpx.AsyncClient) -> dict:
    api_key = os.getenv(model_cfg["api_key_env"])
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_cfg["model_id"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
    }
    if model_cfg.get("thinking"):
        payload["thinking"] = {"type": "enabled"}
    start = time.time()
    resp = await client.post(
        f"{model_cfg['api_base']}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    elapsed = time.time() - start
    data = resp.json()

    if resp.status_code != 200:
        raise Exception(f"DeepSeek API error {resp.status_code}: {data}")

    usage = data.get("usage", {})
    content = data["choices"][0]["message"]["content"]
    return {
        "content": content,
        "tokens_input": usage.get("prompt_tokens", 0),
        "tokens_output": usage.get("completion_tokens", 0),
        "latency_s": round(elapsed, 2),
    }


async def call_minimax(model_cfg: dict, prompt: str, client: httpx.AsyncClient) -> dict:
    api_key = os.getenv(model_cfg["api_key_env"])
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_cfg["model_id"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
    }
    # M2.5 使用 OpenAI 兼容端点
    url = f"{model_cfg['api_base']}/chat/completions"

    start = time.time()
    resp = await client.post(url, headers=headers, json=payload, timeout=120)
    elapsed = time.time() - start
    data = resp.json()

    if resp.status_code != 200:
        raise Exception(f"MiniMax API error {resp.status_code}: {data}")

    usage = data.get("usage", {})
    content = data["choices"][0]["message"]["content"]
    return {
        "content": content,
        "tokens_input": usage.get("prompt_tokens", 0),
        "tokens_output": usage.get("completion_tokens", 0),
        "latency_s": round(elapsed, 2),
    }


async def call_claude(model_cfg: dict, prompt: str, client: httpx.AsyncClient) -> dict:
    api_key = os.getenv(model_cfg["api_key_env"])
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_cfg["model_id"],
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    start = time.time()
    resp = await client.post(
        f"{model_cfg['api_base']}/messages",
        headers=headers,
        json=payload,
        timeout=120,
    )
    elapsed = time.time() - start
    data = resp.json()

    if resp.status_code != 200:
        raise Exception(f"Claude API error {resp.status_code}: {data}")

    usage = data.get("usage", {})
    content = data["content"][0]["text"]
    return {
        "content": content,
        "tokens_input": usage.get("input_tokens", 0),
        "tokens_output": usage.get("output_tokens", 0),
        "latency_s": round(elapsed, 2),
    }


# ── 单次测试 ──────────────────────────────────────────
async def run_single(model_name: str, model_cfg: dict, prompt_item: dict, client: httpx.AsyncClient) -> dict:
    provider = model_cfg["provider"]
    print(f"  → {model_name} ...", end="", flush=True)

    try:
        if provider == "deepseek":
            result = await call_deepseek(model_cfg, prompt_item["prompt"], client)
        elif provider == "minimax":
            result = await call_minimax(model_cfg, prompt_item["prompt"], client)
        elif provider == "anthropic":
            result = await call_claude(model_cfg, prompt_item["prompt"], client)
        else:
            raise Exception(f"未知 provider: {provider}")

        # 计算费用
        cost = (
            result["tokens_input"] / 1_000_000 * model_cfg["price_input"]
            + result["tokens_output"] / 1_000_000 * model_cfg["price_output"]
        )

        record = {
            "prompt_id": prompt_item["id"],
            "scene": prompt_item["scene"],
            "complexity": prompt_item["complexity"],
            "model": model_name,
            "provider": provider,
            "timestamp": datetime.now().isoformat(),
            "latency_s": result["latency_s"],
            "tokens_input": result["tokens_input"],
            "tokens_output": result["tokens_output"],
            "cost_usd": round(cost, 6),
            "output": result["content"],
            "error": None,
            "is_token_plan": model_cfg.get("is_token_plan", False),
            # 评分留空，事后填
            "quality_score": None,
            "usability": None,
            "notes": None,
        }
        print(f" ✓ ({result['latency_s']}s, ${cost:.5f})")

    except Exception as e:
        record = {
            "prompt_id": prompt_item["id"],
            "scene": prompt_item["scene"],
            "complexity": prompt_item["complexity"],
            "model": model_name,
            "provider": provider,
            "timestamp": datetime.now().isoformat(),
            "latency_s": None,
            "tokens_input": 0,
            "tokens_output": 0,
            "cost_usd": 0,
            "output": None,
            "error": str(e),
            "is_token_plan": model_cfg.get("is_token_plan", False),
            "quality_score": None,
            "usability": None,
            "notes": None,
        }
        print(f" ✗ {e}")

    return record


# ── 主流程 ────────────────────────────────────────────
async def main(args):
    prompts_path = Path(__file__).parent / "prompts.json"
    prompts = json.loads(prompts_path.read_text(encoding="utf-8"))

    # 过滤
    if args.prompt_id:
        prompts = [p for p in prompts if p["id"] == args.prompt_id]
    if args.scene:
        prompts = [p for p in prompts if p["scene"] == args.scene]

    models = MODELS
    if args.model:
        models = {k: v for k, v in MODELS.items() if k == args.model}

    # 读取 models_config.json 覆盖 enabled 状态
    if MODELS_CONFIG_FILE.exists():
        try:
            config_data = json.loads(MODELS_CONFIG_FILE.read_text(encoding="utf-8"))
            for name, enabled in config_data.items():
                if name in models:
                    models[name]["enabled"] = enabled
        except Exception:
            pass

    # 过滤：移除已禁用 + 未配置 API Key 的模型
    active_models = {}
    for name, cfg in models.items():
        if not cfg.get("enabled", True):
            print(f"⏭ 跳过 {name}: 已禁用")
            continue
        key = os.getenv(cfg["api_key_env"], "")
        if key and "your_" not in key:
            active_models[name] = cfg
        else:
            print(f"⏭ 跳过 {name}: {cfg['api_key_env']} 未配置")

    if not prompts:
        print("没有匹配的 prompt，请检查参数")
        return
    if not models:
        print(f"没有匹配的模型: {args.model}")
        return

    if not active_models:
        print("没有可用模型（API Key 均未配置），请先编辑 .env")
        return

    # ── 增量检测 ──
    existing = {}  # (model, prompt_id) -> record
    if not args.fresh and LATEST_FILE.exists():
        try:
            old = json.loads(LATEST_FILE.read_text(encoding="utf-8"))
            old_records = old.get("records", old) if isinstance(old, dict) else old
            if isinstance(old_records, list):
                for r in old_records:
                    if isinstance(r, dict) and "model" in r and "prompt_id" in r:
                        existing[(r["model"], r["prompt_id"])] = r
                if existing:
                    print(f"📂 加载已有结果: {len(existing)} 条记录")
        except Exception:
            pass

    # 计算需要新增的测试
    to_test = []
    for prompt_item in prompts:
        for model_name in active_models:
            key = (model_name, prompt_item["id"])
            if key not in existing or args.fresh:
                to_test.append((prompt_item, model_name))

    reused = (len(prompts) * len(active_models)) - len(to_test)
    if reused > 0 and not args.fresh:
        print(f"♻ 复用已有结果: {reused} 条")
    if to_test:
        print(f"🆕 需要测试: {len(to_test)} 条\n")
    elif not args.fresh:
        print("✅ 所有组合均已测试，无需重跑")
        print(f"   结果文件: {LATEST_FILE}")
        # 确保 skipped 是最新的
        _save_latest(existing, active_models, models)
        return

    new_results = []
    async with httpx.AsyncClient() as client:
        # 按 prompt 分组输出
        tested_pids = set()
        for prompt_item, model_name in to_test:
            model_cfg = active_models[model_name]
            if prompt_item["id"] not in tested_pids:
                if tested_pids:
                    print()
                print(f"[{prompt_item['id']}] {prompt_item['scene']} | {prompt_item['prompt'][:40]}...")
                tested_pids.add(prompt_item["id"])
            record = await run_single(model_name, model_cfg, prompt_item, client)
            new_results.append(record)

    if tested_pids:
        print()

    _save_latest(existing, active_models, models, new_results)


def _save_latest(existing, active_models, all_models, new_results=None):
    """合并已有记录+新记录，只保留 active_models 的数据"""
    records = {}
    # 旧记录：只保留当前 active_models 中存在的
    for (model, pid), r in existing.items():
        if model in active_models:
            records[(model, pid)] = r
    # 新记录覆盖
    if new_results:
        for r in new_results:
            records[(r["model"], r["prompt_id"])] = r

    all_records = list(records.values())
    skipped = [name for name in all_models if name not in active_models]

    # 同时保存到 latest.json 和时间戳文件
    output = {"records": all_records, "skipped": skipped}
    LATEST_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = RESULTS_DIR / f"run_{ts}.json"
    backup_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"结果已保存: {LATEST_FILE}")
    print(f"备份: {backup_path}")
    print(f"\n下一步: python score_server.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="指定模型 (deepseek-v4-flash / deepseek-v4-flash-think / deepseek-v4-pro / minimax / claude-sonnet)")
    parser.add_argument("--scene", help="指定场景 (前端开发 / 工具/自动化 / Web工具)")
    parser.add_argument("--prompt-id", help="指定 prompt ID")
    parser.add_argument("--fresh", action="store_true", help="忽略已有结果，全部重跑")
    args = parser.parse_args()
    asyncio.run(main(args))
