# LLM Benchmark

对同一批真实需求，同时测试多个 LLM 模型，自动采集耗时、费用、Token 用量等指标，提供 Web 端评分与汇总对比。

## 快速开始

### 1. 环境要求
- Python 3.10+
- 可选：Claude Code CLI（如需测试 claude-code 模型）
- 可选：OpenAI Codex CLI（如需测试 codex 模型）`npm i -g @openai/codex`

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置 API Key
```bash
cp .env.example .env
# 编辑 .env，填入你需要的 API Key（至少配一个）
```

支持的模型：
| 模型 | 环境变量 | 说明 |
|------|----------|------|
| deepseek-v4-flash | `DEEPSEEK_API_KEY` | DeepSeek V4 Flash |
| deepseek-v4-pro | `DEEPSEEK_API_KEY` | DeepSeek V4 Pro |
| minimax (M2.5) | `MINIMAX_API_KEY` + `MINIMAX_GROUP_ID` | MiniMax Token Plan |
| minimax-m2.7 | `MINIMAX_API_KEY` + `MINIMAX_GROUP_ID` | MiniMax M2.7 |
| claude-sonnet | `CLAUDE_API_KEY` | Claude Sonnet 4.5 |
| claude-code | 需安装 Claude Code CLI | 通过 CLI 调用 |
| codex | 需安装 `@openai/codex` | 通过 CLI 调用 |

仅配置了有效 API Key 的模型才会运行，未配置的自动跳过。

### 4. 运行测试
```bash
# 跑所有已配置 Key 的模型 × 所有 prompt
python runner.py

# 只跑指定模型
python runner.py --model deepseek-v4-flash

# 只跑指定场景
python runner.py --scene 前端开发

# 强制重新运行（忽略已有结果）
python runner.py --fresh
```

支持增量测试：已有结果自动复用，只跑新增/未完成的组合。

### 5. 查看结果 & 评分

**Web 界面（推荐）**：
```bash
python score_server.py
# 自动打开浏览器 → http://127.0.0.1:8765
```

Web 端功能：
- **评分页** (`/`) — 逐条查看模型输出，打质量分（1-5）和可用度
- **汇总页** (`/summary.html`) — 所有历史结果汇总对比
- **模型管理** (`/models.html`) — 启用/禁用模型，控制汇总页显示
- **计费设置** (`/billing.html`) — 配置汇率（USD/RMB）、Token Plan 费用统计

**命令行**：
```bash
python report.py                           # 查看最新结果
python report.py --compare                 # 汇总历史对比
python report.py --file results/xxx.json --score  # 命令行评分
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
1. 在 `runner.py` 的 `MODELS` 字典中添加模型配置
2. 实现对应的 `call_xxx()` 异步函数
3. 在 `score_server.py` 的 `MODELS_DETAIL` 和 `ALL_MODELS` 中注册

## 目录结构
```
llm-benchmark/
├── prompts.json          # 测试需求
├── runner.py             # 核心测试引擎
├── report.py             # 命令行报告 & 评分
├── score_server.py       # Web 评分服务
├── score.html            # 评分页面
├── summary.html          # 汇总对比页
├── models.html           # 模型管理页
├── billing.html          # 计费设置页
├── call_claude_code.py   # Claude Code CLI 调用器
├── call_codex.py         # Codex CLI 调用器
├── requirements.txt      # Python 依赖
├── .env.example          # API Key 模板
└── test/                 # 单元测试
```
