# 功能测试框架搭建

## 任务 1：环境准备
- `requirements.txt` 追加 `pytest>=8.0.0`
- 创建 `test/` 目录 + `test/__init__.py`
- 创建 `test/conftest.py` 放共享 fixture（临时目录、示例数据）

## 任务 2：`test/test_report.py`
测试 `report.py` 的 `_load_records` / `_save_records`：
- 旧列表格式 `[{...}]` 正确解析为 `(records, [])`
- 新字典格式 `{"records":[...], "skipped":[...]}` 正确拆分
- 空文件 / 异常输入返回空元组
- `_save_records` 有 skipped 时写字典格式，无 skipped 写列表格式

## 任务 3：`test/test_runner.py`
测试 `runner.py` 的模型过滤与 `_save_latest`：
- `enabled=True` + 有 API Key → 进入 active_models
- `enabled=False` → 跳过
- 有 API Key 但 enabled 被 `models_config.json` 覆盖为 False → 跳过
- `_save_latest` 合并新旧记录，正确生成 skipped 列表

## 任务 4：`test/test_score_server.py`
测试 `score_server.py` 的 ScoreHandler（用 `http.server` 内置测试方式或直接测方法）：
- `_list_files` 返回 latest.json + run_*/claude_code_*/codex_* 文件
- `_load_file` 兼容新旧格式，返回含 `_skipped` 标记的列表
- `_save_file` 正确写回 `{"records":[], "skipped":[]}` 格式
- `_summary` 聚合多个文件的 records 和 skipped
- `_get_prompts` 返回 prompts.json 内容
