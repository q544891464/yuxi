"""事实证据审查的输入、模型结果与交付契约。"""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Risk = Literal["low", "medium", "high"]
Sufficiency = Literal["sufficient", "basically_sufficient", "doubtful", "insufficient"]
Relation = Literal["direct", "indirect", "corroborative", "supporting", "duplicate", "conflicting"]


class SourceReference(BaseModel):
    """保留材料中实际提供的定位信息。"""

    model_config = ConfigDict(extra="forbid")
    document: str = ""
    section: str = ""
    evidence_id: str = ""
    file_path: str = ""
    page: int | None = Field(default=None, ge=1)
    paragraph_id: str = ""
    chunk_id: str = ""


class Violation(BaseModel):
    """兼容解析 Skill 的违法事项并保留其他案件字段。"""

    model_config = ConfigDict(extra="allow")
    violation_id: str = Field(min_length=1)
    behavior: str = ""
    fact_summary: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    source_reference: SourceReference | None = None


class CaseEvidence(BaseModel):
    """案件材料中的证据及其关联事项。"""

    model_config = ConfigDict(extra="allow")
    evidence_id: str = Field(min_length=1)
    name: str = ""
    type: str = ""
    proves: str = ""
    related_violation_ids: list[str] = Field(default_factory=list)
    source_reference: SourceReference | None = None


class CaseJSON(BaseModel):
    """接收前置解析结果，允许保留不属于本岗位审查范围的字段。"""

    model_config = ConfigDict(extra="allow")
    violations: list[Violation] = Field(default_factory=list)
    evidence: list[CaseEvidence] = Field(default_factory=list)
    source_trace: list[dict[str, Any]] = Field(default_factory=list)
    statement_and_defense: Any = None

    @model_validator(mode="before")
    @classmethod
    def require_case(cls, value):
        """在协议入口拒绝空案件。"""
        if not isinstance(value, dict) or not value:
            raise ValueError("Case JSON 为空，请先使用稽查报告结构化解析 Skill。")
        return value

    @model_validator(mode="after")
    def unique_identifiers(self):
        """避免重复标识使证据或事项映射失真。"""
        for items, key in ((self.violations, "violation_id"), (self.evidence, "evidence_id")):
            ids = [getattr(item, key) for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{key} 不得重复")
        return self


class OriginalMaterial(BaseModel):
    """读取既有文件后端中的原文文本窗口。"""

    model_config = ConfigDict(extra="forbid")
    file_path: str = Field(min_length=1)
    document: str = ""
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=2000, ge=1, le=4000)


class EvidenceReviewInput(BaseModel):
    """主 Agent 以 JSON 字符串作为 task.description 传入此结构。"""

    model_config = ConfigDict(extra="forbid")
    case_json: CaseJSON
    original_materials: list[OriginalMaterial] = Field(default_factory=list, max_length=10)


def parse_review_input(content: str) -> EvidenceReviewInput:
    """读取 task JSON，并识别 chat_service 追加的附件上下文。"""
    text = content.lstrip()
    payload, end = json.JSONDecoder().raw_decode(text)
    suffix = text[end:].strip()
    if suffix and not (suffix.startswith("<attachment_context>\n") and suffix.endswith("\n</attachment_context>")):
        raise ValueError("审查输入必须是完整 JSON，不能附加自然语言指令。")
    return EvidenceReviewInput.model_validate(payload)


class ReviewModel(BaseModel):
    """模型输出仅允许声明的审查字段。"""

    model_config = ConfigDict(extra="forbid")


class EvidenceMapping(ReviewModel):
    """一份证据对当前待证事实的证明作用。"""

    evidence_id: str
    name: str
    type: str
    proves: str
    relation: Relation
    source_reference: SourceReference | None = None


class FactReview(ReviewModel):
    """待证事实的独立审查结论。"""

    fact_id: str = Field(min_length=1)
    fact: str = Field(min_length=1)
    importance: Literal["core", "supporting"]
    evidence: list[EvidenceMapping]
    evidence_analysis: str
    conclusion: Sufficiency
    risk_level: Risk
    issues: list[str]
    missing_evidence: list[str]
    recommendation: str
    source_reference: SourceReference | None = None


class ViolationReview(ReviewModel):
    """单项违法事项及其待证事实。"""

    violation_id: str
    violation_name: str
    inspection_fact: str
    fact_reviews: list[FactReview] = Field(min_length=1)
    overall_conclusion: str
    overall_risk: Risk


class EvidenceConflict(ReviewModel):
    """保留两份证据的分歧与影响。"""

    evidence_a: str = Field(description="第一份证据的 evidence_id，必须来自 Case JSON，不是证据名称或报告认定。")
    evidence_b: str = Field(
        description="第二份不同证据的 evidence_id。报告认定与证据的差异写入 evidence_gaps/review_findings。"
    )
    conflict: str
    impact: str
    risk_level: Risk
    source_reference: SourceReference | None = None


class EvidenceGap(ReviewModel):
    """事实对应的材料缺口。"""

    fact: str
    missing: str
    impact: str
    recommendation: str
    source_reference: SourceReference | None = None


class ReviewFinding(ReviewModel):
    """交给主 Agent 汇总的审查发现。"""

    title: str
    type: Literal["evidence_gap", "evidence_conflict", "weak_evidence", "unmatched_fact", "other"]
    risk_level: Risk
    description: str
    recommendation: str
    source_reference: SourceReference | None = None


class ReviewAnalysis(ReviewModel):
    """模型负责分析，汇总计数由程序计算。"""

    violation_reviews: list[ViolationReview]
    evidence_conflicts: list[EvidenceConflict]
    evidence_gaps: list[EvidenceGap]
    review_findings: list[ReviewFinding]


class ReviewSummary(ReviewModel):
    """各充分程度与高风险待证事实的数量。"""

    violation_count: int
    fact_count: int
    sufficient_count: int
    basically_sufficient_count: int
    doubtful_count: int
    insufficient_count: int
    high_risk_count: int


class FactEvidenceReviewResult(ReviewAnalysis):
    """经验证的子任务结果，不包含全局案件结论。"""

    review_type: Literal["fact_evidence_review"] = "fact_evidence_review"
    overall_status: Literal["pass", "warning", "risk"]
    summary: ReviewSummary
    message: str = ""
    limitations: list[str]
