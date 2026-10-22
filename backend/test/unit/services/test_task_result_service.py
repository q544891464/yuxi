"""文件结果摘要必须由明细证明，不能由任务终态或乐观计数推导。"""

import pytest

from yuxi.services.task_result_service import summarize_file_result

pytestmark = pytest.mark.unit


def test_partial_failure_uses_file_records_not_optimistic_failed_counter():
    """捕获后返回的文件错误不能被 failed=0 隐藏。"""
    summary = summarize_file_result(
        "knowledge_parse",
        {"file_ids": ["ok", "bad", "pending", "missing"]},
        {
            "processed": 4,
            "failed": 0,
            "items": [
                {"file_id": "ok", "status": "parsed"},
                {"file_id": "bad", "status": "error_parsing", "error_message": "格式不支持"},
                {"file_id": "pending", "status": "uploaded"},
            ],
        },
    )
    assert summary == {
        "total": 4,
        "recorded": 3,
        "succeeded": 1,
        "failed": 1,
        "pending": 1,
        "unknown": 1,
        "has_result": True,
        "truncated": False,
    }


@pytest.mark.parametrize(
    "task_type,payload,expected",
    [
        ("knowledge_parse", {}, 1),
        ("knowledge_index", {}, 0),
        ("knowledge_ingest", {"params": {"auto_index": True}}, 0),
        ("knowledge_ingest", {"params": {"auto_index": False}}, 1),
    ],
)
def test_parsed_only_satisfies_a_parse_task(task_type, payload, expected):
    """已解析对入库任务仍是待处理，不能视为成功。"""
    summary = summarize_file_result(task_type, payload, {"items": [{"status": "parsed"}]})
    assert summary["succeeded"] == expected
    assert summary["pending"] == 1 - expected


def test_missing_and_truncated_results_remain_unknown():
    """无结果或截断时不使用 processed-failed 伪造成功数。"""
    missing = summarize_file_result("knowledge_index", {"file_ids": ["one", "two"]}, None)
    assert missing["has_result"] is False
    assert missing["unknown"] == 2
    assert missing["succeeded"] == 0
    assert summarize_file_result("knowledge_parse", {}, None)["total"] is None

    result = {"processed": 250, "failed": 0, "result_truncated": True, "items": [{"status": "indexed"}] * 200}
    truncated = summarize_file_result("knowledge_index", {}, result)
    assert truncated["succeeded"] == 200
    assert truncated["unknown"] == 50
    assert truncated["truncated"] is True
    del result["processed"]
    assert summarize_file_result("knowledge_index", {}, result)["total"] is None


def test_error_without_file_id_and_unrecognized_records_are_not_successful():
    """旧错误记录保留失败，缺少状态的旧记录保留待核对。"""
    summary = summarize_file_result(
        "knowledge_ingest",
        {},
        {
            "items": [
                {"item": "failed.txt", "error": "无法解析"},
                {"status": "future"},
                None,
            ]
        },
    )
    assert summary["failed"] == 1
    assert summary["unknown"] == 2
    assert summary["succeeded"] == 0


def test_empty_result_and_non_file_task_are_distinct():
    """显式空结果与非文件任务不生成虚假文件成功数。"""
    empty = summarize_file_result("knowledge_parse", {}, {"processed": 0, "items": []})
    assert empty["total"] == 0
    assert empty["has_result"] is True
    assert summarize_file_result("rag_evaluation", {}, {"score": 0.9}) is None
