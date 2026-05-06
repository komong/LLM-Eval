"""测试 report.py 的 _load_records / _save_records 格式兼容"""

import json
from pathlib import Path

from report import _load_records, _save_records


class TestLoadRecords:
    """_load_records 格式兼容测试"""

    def test_old_list_format(self, old_format_file, sample_records):
        """旧列表格式 [{...}] 正确解析"""
        records, skipped = _load_records(old_format_file)
        assert records == sample_records
        assert skipped == []

    def test_new_dict_format(self, new_format_file, sample_records, skipped_models):
        """新字典格式 {"records":[...], "skipped":[...]} 正确拆分"""
        records, skipped = _load_records(new_format_file)
        assert records == sample_records
        assert skipped == skipped_models

    def test_empty_file_returns_empty(self, tmp_dir):
        """空列表文件返回空"""
        p = tmp_dir / "empty.json"
        p.write_text("[]", encoding="utf-8")
        records, skipped = _load_records(p)
        assert records == []
        assert skipped == []

    def test_invalid_json_raises(self, tmp_dir):
        """非法 JSON 抛出异常"""
        p = tmp_dir / "bad.json"
        p.write_text("not json", encoding="utf-8")
        with __import__("pytest").raises(json.JSONDecodeError):
            _load_records(p)


class TestSaveRecords:
    """_save_records 格式保存测试"""

    def test_save_with_skipped_writes_dict_format(self, tmp_dir, sample_records, skipped_models):
        """有 skipped 时写字典格式"""
        p = tmp_dir / "out.json"
        _save_records(p, sample_records, skipped_models)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert data["records"] == sample_records
        assert data["skipped"] == skipped_models

    def test_save_without_skipped_writes_list_format(self, tmp_dir, sample_records):
        """无 skipped 时写列表格式"""
        p = tmp_dir / "out.json"
        _save_records(p, sample_records, [])
        data = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert data == sample_records

    def test_roundtrip_new_format(self, tmp_dir, sample_records, skipped_models):
        """写-读回环：新格式保持一致"""
        p = tmp_dir / "roundtrip.json"
        _save_records(p, sample_records, skipped_models)
        records, skipped = _load_records(p)
        assert records == sample_records
        assert skipped == skipped_models

    def test_roundtrip_old_format(self, tmp_dir, sample_records):
        """写-读回环：旧格式保持一致"""
        p = tmp_dir / "roundtrip.json"
        _save_records(p, sample_records, [])
        records, skipped = _load_records(p)
        assert records == sample_records
        assert skipped == []
