# LLM Benchmark

对同一批真实需求，同时测试多个模型，自动记录耗时、费用、token 用量，事后统一评分对比。

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 API Key
```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 3. 跑测试
```bash
# 跑所有模型 × 所有 prompt
python runner.py

# 只跑指定模型
python runner.py --model deepseek-v4-flash

# 只跑指定场景
python runner.py --scene 前端开发

# 只跑指定 prompt
python runner.py --prompt-id frontend_001
```

### 4. 查看结果 & 评分
```bash
# 查看最新结果报告
python report.py

# 查看指定结果
python report.py --file results/run_20260506_120000.json

# 进入评分模式（看输出，打质量分）
python report.py --file results/run_20260506_120000.json --score

# 汇总所有历史结果对比
python report.py --compare
```

## 添加新 Prompt
编辑 `prompts.json`，按以下格式添加：
```json
{
  "id": "唯一ID",
  "scene": "场景名称",
  "complexity": "low / medium / high",
  "prompt": "你的真实需求原文"
}
```

## 添加新模型
编辑 `runner.py` 中的 `MODELS` 字典，按现有格式添加即可。

## 目录结构
```
llm-benchmark/
├── prompts.json          # 测试用的需求原文
├── results/              # 每次测试的原始输出（自动生成）
├── runner.py             # 主程序
├── report.py             # 报告 & 评分 (命令行)
├── score_server.py       # 评分 HTTP 服务
├── score.html            # 评分页面
├── summary.html          # 汇总页
├── requirements.txt
├── .env.example
└── .env                  # 你的 API Key（不要提交到 git）
```
