"""将知识文件任务的持久结果投影为有界摘要，不改变执行状态。"""

from typing import Any


def summarize_file_result(task_type: str, payload: dict, result: Any) -> dict | None:
    """仅统计有记录的文件结果，缺失及截断记录保留为待核对。"""
    if task_type not in {"knowledge_ingest", "knowledge_parse", "knowledge_index"}:
        return None

    result = result if isinstance(result, dict) else {}
    items = result.get("items")
    has_result = isinstance(items, list)
    items = items if has_result else []
    total = result.get("processed", result.get("submitted"))
    total = total if isinstance(total, int) and total >= 0 else None
    submitted = payload.get("file_ids", payload.get("items"))
    if isinstance(submitted, list):
        total = max(total or 0, len(submitted))
    if has_result and (total is not None or not result.get("result_truncated")):
        total = max(total or 0, len(items))

    counts = {"succeeded": 0, "failed": 0, "pending": 0, "unknown": 0}
    needs_index = task_type == "knowledge_index" or (
        task_type == "knowledge_ingest" and bool((payload.get("params") or {}).get("auto_index"))
    )
    for item in items:
        if not isinstance(item, dict):
            counts["unknown"] += 1
            continue
        status = item.get("status")
        if status in {"failed", "error_parsing", "error_indexing"} or item.get("error") or item.get("error_message"):
            counts["failed"] += 1
        elif status in {"indexed", "done"} or (status == "parsed" and not needs_index):
            counts["succeeded"] += 1
        elif status in {"uploaded", "parsing", "parsed", "indexing", "processing", "waiting"}:
            counts["pending"] += 1
        else:
            counts["unknown"] += 1
    counts["unknown"] += max(0, (total or 0) - len(items))
    return {
        **counts,
        "total": total,
        "recorded": len(items),
        "has_result": has_result,
        "truncated": bool(result.get("result_truncated")),
    }
