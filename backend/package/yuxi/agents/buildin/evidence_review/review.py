"""执行事实证据审查并在模型边界校验结果。"""

import json

from .prompt import SYSTEM_PROMPT
from .schema import (
    EvidenceGap,
    EvidenceReviewInput,
    FactEvidenceReviewResult,
    FactReview,
    ReviewAnalysis,
    ReviewFinding,
    ReviewSummary,
    SourceReference,
    ViolationReview,
)


def linked_evidence_ids(case, violation):
    """只允许明确关联到当前违法事项的已知证据。"""
    return {
        item.evidence_id
        for item in case.evidence
        if item.evidence_id in violation.evidence_ids or violation.violation_id in item.related_violation_ids
    }


def missing_evidence_review(violation, read_paths=()):
    """无关联证据时直接返回不足，避免模型凭空补证。"""
    issue = "当前违法事实未关联可识别证据。当前材料不足以确认。"
    return ViolationReview(
        violation_id=violation.violation_id,
        violation_name=violation.behavior or violation.violation_id,
        inspection_fact=violation.fact_summary,
        fact_reviews=[
            FactReview(
                fact_id=f"{violation.violation_id}-F1",
                fact=violation.fact_summary or violation.behavior or "报告未提供具体事实",
                importance="core",
                evidence=[],
                evidence_analysis=issue,
                conclusion="insufficient",
                risk_level="high",
                issues=[issue],
                missing_evidence=["与当前违法事项关联的原始证据及其证明内容"],
                recommendation="补充具体事实、证据清单及事实与证据的对应关系。",
                source_reference=case_source_reference(violation.source_reference, read_paths),
            )
        ],
        overall_conclusion=issue,
        overall_risk="high",
    )


def case_source_reference(reference, read_paths):
    """保留结构化来源位置，仅对实际读取过的原文提供文件链接。"""
    if reference is None:
        return None
    return reference.model_copy(update={"file_path": reference.file_path if reference.file_path in read_paths else ""})


async def review_evidence(request: EvidenceReviewInput, model, backend) -> FactEvidenceReviewResult:
    """复用授权文件后端读取原文，再调用模型执行限定范围的分析。"""
    case = request.case_json
    originals = []
    limitations = []
    for material in request.original_materials:
        # 路径权限、虚拟路径归一化与附件格式处理归既有 filesystem boundary。
        read = await backend.aread(material.file_path, offset=material.offset, limit=material.limit)
        if read.error or not read.file_data or not read.file_data.get("content"):
            limitations.append(f"未能回查原始材料：{material.document or material.file_path}")
            continue
        content = read.file_data["content"]
        if read.file_data.get("encoding") == "base64":
            limitations.append(f"未能回查原始材料：{material.document or material.file_path}（请提供解析后的文本）")
            continue
        originals.append({**material.model_dump(), "content": content})
        limitations.append(
            f"原文核查范围：{material.document or material.file_path}，"
            f"起始行 {material.offset + 1}，最多 {material.limit} 行。"
        )
    if not request.original_materials:
        limitations.append("未能回查原始材料：未提供原文路径，本次仅依据 Case JSON。")
    read_paths = {item["file_path"] for item in originals}

    reviewable = [v for v in case.violations if linked_evidence_ids(case, v)]
    if not reviewable:
        analysis = ReviewAnalysis(
            violation_reviews=[missing_evidence_review(v, read_paths) for v in case.violations],
            evidence_conflicts=[],
            evidence_gaps=[],
            review_findings=[],
        )
        return finalize_review(request, analysis, limitations, read_paths)

    # 模型只处理有关联材料的事项；无证据事项由程序给出确定性结果。
    case_data = case.model_dump()
    case_data["violations"] = [v.model_dump() for v in reviewable]
    for item in [*case_data["violations"], *case_data["evidence"]]:
        if item.get("source_reference") and item["source_reference"]["file_path"] not in read_paths:
            item["source_reference"]["file_path"] = ""
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", json.dumps({"case_json": case_data, "original_materials": originals}, ensure_ascii=False)),
    ]
    structured_model = model.with_structured_output(ReviewAnalysis, method="function_calling")
    expected = {v.violation_id for v in reviewable}
    for attempt in range(2):
        try:
            candidate = await structured_model.ainvoke(messages, config={"tags": ["nostream"]})
            analysis = ReviewAnalysis.model_validate(candidate)
            actual = [v.violation_id for v in analysis.violation_reviews]
            if len(actual) != len(set(actual)) or set(actual) != expected:
                raise ValueError("事实证据审查结果未完整对应输入违法事项，请重新审查。")
            analysis.violation_reviews.extend(
                missing_evidence_review(v, read_paths) for v in case.violations if v.violation_id not in expected
            )
            return finalize_review(request, analysis, limitations, read_paths)
        except ValueError as exc:
            if attempt:
                raise ValueError("事实证据审查输出连续两次未通过校验，未生成有效审查结果。") from exc
            # 只纠正模型结构/引用错误；连接、超时和文件错误不在这里重试。
            messages.append(
                ("human", f"上次输出未通过校验：{str(exc)[:1000]}。请重新给出完整结果，遵守 Schema 和证据 ID。")
            )
    raise AssertionError("不可达的审查分支")


def finalize_review(
    request, analysis: ReviewAnalysis, limitations: list[str], read_paths=None
) -> FactEvidenceReviewResult:
    """校验证据与定位标识，并从事实结果计算汇总。"""
    case = request.case_json
    violations = {v.violation_id: v for v in case.violations}
    evidence = {e.evidence_id: e for e in case.evidence}
    read_paths = read_paths or set()
    ids = [v.violation_id for v in analysis.violation_reviews]
    if len(ids) != len(set(ids)) or set(ids) != set(violations):
        raise ValueError("审查结果必须逐项对应输入违法事项。")
    references = [SourceReference(evidence_id=e.evidence_id) for e in case.evidence]
    references.extend(
        case_source_reference(item.source_reference, read_paths)
        for item in [*case.evidence, *case.violations]
        if item.source_reference
    )
    original_refs = [
        SourceReference(document=m.document, file_path=m.file_path)
        for m in request.original_materials
        if m.file_path in read_paths
    ]
    references.extend(original_refs)
    references.extend(
        SourceReference(document=str(trace.get("document") or ""), section=str(trace.get("source_section") or ""))
        for trace in case.source_trace
    )
    known_refs = {ref.model_dump_json() for ref in references}
    facts = []
    risk_order = {"low": 0, "medium": 1, "high": 2}
    for item in analysis.violation_reviews:
        violation = violations[item.violation_id]
        item.inspection_fact = violation.fact_summary
        allowed_ids = linked_evidence_ids(case, violation)
        allowed_refs = [SourceReference(evidence_id=eid) for eid in allowed_ids] + original_refs
        allowed_refs.extend(
            case_source_reference(evidence[eid].source_reference, read_paths)
            for eid in allowed_ids
            if evidence[eid].source_reference
        )
        if violation.source_reference:
            allowed_refs.append(case_source_reference(violation.source_reference, read_paths))
        violation_index = next(i for i, v in enumerate(case.violations) if v.violation_id == item.violation_id)
        allowed_refs.extend(
            SourceReference(document=str(trace.get("document") or ""), section=str(trace.get("source_section") or ""))
            for trace in case.source_trace
            if str(trace.get("field") or "").startswith(f"violations[{violation_index}]")
        )
        fact_refs = {ref.model_dump_json() for ref in allowed_refs}
        fact_ids = [fact.fact_id for fact in item.fact_reviews]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("同一事项的待证事实标识不得重复。")
        for fact in item.fact_reviews:
            if fact.source_reference and fact.source_reference.model_dump_json() not in fact_refs:
                raise ValueError("待证事实引用了其他事项或未回查的原文来源。")
            for mapping in fact.evidence:
                if mapping.evidence_id not in allowed_ids:
                    raise ValueError("审查结果引用了不存在或未关联到当前事项的证据。")
                origin = evidence[mapping.evidence_id]
                mapping.name, mapping.type, mapping.proves = origin.name, origin.type, origin.proves
                mapping.source_reference = case_source_reference(
                    origin.source_reference, read_paths
                ) or SourceReference(evidence_id=origin.evidence_id)
            if not fact.evidence:
                fact.conclusion, fact.risk_level = "insufficient", "high"
                issue = "当前违法事实未关联可识别证据。当前材料不足以确认。"
                if issue not in fact.issues:
                    fact.issues.append(issue)
                if not fact.missing_evidence:
                    fact.missing_evidence.append("能够支持当前待证事实的证据")
                analysis.review_findings.append(
                    ReviewFinding(
                        title=fact.fact,
                        type="evidence_gap",
                        risk_level="high",
                        description=issue,
                        recommendation=fact.recommendation,
                        source_reference=fact.source_reference,
                    )
                )
                analysis.evidence_gaps.append(
                    EvidenceGap(
                        fact=fact.fact,
                        missing="；".join(fact.missing_evidence),
                        impact=issue,
                        recommendation=fact.recommendation,
                        source_reference=fact.source_reference,
                    )
                )
            if fact.conclusion == "insufficient":
                fact.risk_level = "high"
            elif fact.conclusion == "doubtful" and fact.risk_level == "low":
                fact.risk_level = "medium"
            facts.append(fact)
        item.overall_risk = max([item.overall_risk, *(f.risk_level for f in item.fact_reviews)], key=risk_order.get)
        conclusions = {fact.conclusion for fact in item.fact_reviews}
        item.overall_conclusion = next(
            label
            for level, label in [
                ("insufficient", "证据不足：存在当前材料不足以确认的待证事实，请逐项补证。"),
                ("doubtful", "存在疑点：部分待证事实需要进一步核对证据。"),
                ("basically_sufficient", "基本充分：请关注各项事实的补强建议。"),
                ("sufficient", "所列待证事实的证据充分；本意见仅涉及事实与证据。"),
            ]
            if level in conclusions
        )

    for conflict in analysis.evidence_conflicts:
        if conflict.evidence_a not in evidence or conflict.evidence_b not in evidence:
            raise ValueError("证据冲突引用了未知证据标识。")
        if conflict.evidence_a == conflict.evidence_b:
            raise ValueError("证据冲突必须保留两份不同证据。")
    for item in [*facts, *analysis.evidence_conflicts, *analysis.evidence_gaps, *analysis.review_findings]:
        if item.source_reference and item.source_reference.model_dump_json() not in known_refs:
            raise ValueError("审查结果引用了输入未提供的材料定位。")
    risks = [f.risk_level for f in facts] + [
        f.risk_level for f in analysis.review_findings + analysis.evidence_conflicts
    ]
    risks.extend(v.overall_risk for v in analysis.violation_reviews)
    incomplete_sources = any("未能回查" in limitation for limitation in limitations)
    status = "risk" if "high" in risks else "warning" if "medium" in risks or incomplete_sources else "pass"
    return FactEvidenceReviewResult(
        **analysis.model_dump(),
        overall_status=status,
        summary=ReviewSummary(
            violation_count=len(violations),
            fact_count=len(facts),
            sufficient_count=sum(f.conclusion == "sufficient" for f in facts),
            basically_sufficient_count=sum(f.conclusion == "basically_sufficient" for f in facts),
            doubtful_count=sum(f.conclusion == "doubtful" for f in facts),
            insufficient_count=sum(f.conclusion == "insufficient" for f in facts),
            high_risk_count=sum(f.risk_level == "high" for f in facts),
        ),
        message="未发现可审查违法事项" if not violations else "",
        limitations=limitations,
    )
