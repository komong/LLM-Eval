#!/usr/bin/env python3
"""
Claude Code 调用器 - 将 Claude Code 作为测试模型运行
用法:
  python call_claude_code.py                      # 运行所有 prompt
  python call_claude_code.py --prompt-id frontend_001  # 只跑指定 prompt
"""

import os
import json
import asyncio
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"


async def call_claude_code(prompt: str) -> dict:
    """调用 Claude Code CLI 并获取输出"""
    import time
    start = time.time()
    
    try:
        # Claude Code CLI 命令 (--print 模式直接输出，不交互)
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True,
            text=True,
            timeout=180,
            encoding="utf-8"
        )
        elapsed = time.time() - start
        
        if result.returncode != 0:
            raise Exception(f"Claude Code error: {result.stderr}")
        
        return {
            "content": result.stdout.strip(),
            "success": True,
            "latency_s": round(elapsed, 2),
        }
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        raise Exception(f"Claude Code 超时 (>{180}s)")
    except FileNotFoundError:
        raise Exception("未找到 claude 命令，请确保 Claude Code CLI 已安装并配置在 PATH 中")


async def run_single(prompt_item: dict) -> dict:
    prompt = prompt_item["prompt"]
    print(f"  → Claude Code ...", end="", flush=True)
    
    try:
        result = await call_claude_code(prompt)
        record = {
            "prompt_id": prompt_item["id"],
            "scene": prompt_item["scene"],
            "complexity": prompt_item["complexity"],
            "model": "claude-code",
            "provider": "claude-code-cli",
            "timestamp": datetime.now().isoformat(),
            "latency_s": result["latency_s"],
            "tokens_input": 0,  # CLI 模式无法获取 token 数
            "tokens_output": 0,
            "cost_usd": 0,
            "output": result["content"],
            "error": None,
            "quality_score": None,
            "usability": None,
            "notes": None,
        }
        print(f" ✓ ({result['latency_s']}s)")
    except Exception as e:
        record = {
            "prompt_id": prompt_item["id"],
            "scene": prompt_item["scene"],
            "complexity": prompt_item["complexity"],
            "model": "claude-code",
            "provider": "claude-code-cli",
            "timestamp": datetime.now().isoformat(),
            "latency_s": None,
            "tokens_input": 0,
            "tokens_output": 0,
            "cost_usd": 0,
            "output": None,
            "error": str(e),
            "quality_score": None,
            "usability": None,
            "notes": None,
        }
        print(f" ✗ {e}")
    
    return record


async def main(args):
    prompts_path = Path(__file__).parent / "prompts.json"
    prompts = json.loads(prompts_path.read_text(encoding="utf-8"))
    
    # 过滤
    if args.prompt_id:
        prompts = [p for p in prompts if p["id"] == args.prompt_id]
    if args.scene:
        prompts = [p for p in prompts if p["scene"] == args.scene]
    
    if not prompts:
        print("没有匹配的 prompt")
        return
    
    print(f"\nClaude Code 测试: {len(prompts)} 个 prompt\n")
    
    all_results = []
    for prompt_item in prompts:
        print(f"[{prompt_item['id']}] {prompt_item['scene']}")
        record = await run_single(prompt_item)
        all_results.append(record)
        print()
    
    # 保存结果
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"claude_code_{ts}.json"
    output = {"records": all_results}
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已保存: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", help="指定场景")
    parser.add_argument("--prompt-id", help="指定 prompt ID")
    args = parser.parse_args()
    asyncio.run(main(args))
