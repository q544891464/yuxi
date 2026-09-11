"""可选真实模型探针：验证六类合成案件，不替代 HTTP/worker E2E。"""

import os

import pytest
from langchain_openai import ChatOpenAI

from yuxi.agents.buildin.evidence_review.review import review_evidence
from yuxi.agents.buildin.evidence_review.schema import EvidenceReviewInput


CASES = [
    (
        "corroboration",
        "仅审查事实：甲企业于2025年3月收到乙客户货款80万元。",
        [
            ("E1", "企业银行流水", "银行流水", "2025年3月10日乙公司向甲企业对公账户支付货款800000元，附言合同HT001。"),
            (
                "E2",
                "乙公司付款凭证",
                "客户会计凭证",
                "乙公司独立提供付款凭证：2025年3月10日支付甲企业货款800000元，合同HT001。",
            ),
            (
                "E3",
                "销售合同及交货单",
                "合同",
                "甲乙合同HT001价款800000元，2025年3月已交货验收，与银行交易号TX001一致。",
            ),
        ],
    ),
    (
        "single_statement",
        "甲企业2025年3月取得未申报销售收入100万元。",
        [
            ("E1", "经营人自述", "自述材料", "经营人自述取得未申报销售收入100万元，并签署无异议。未提供其他材料。"),
        ],
    ),
    (
        "amount_gap",
        "甲企业2025年3月销售收入收款总额100万元。",
        [
            ("E1", "银行流水", "银行流水", "银行流水逐笔合计800000元，均为本期销售收款，无其他收款记录。"),
            ("E2", "销售记录", "销售台账", "与流水对应的销售记录合计800000元，无法找到剩余200000元的销售及收款记录。"),
        ],
    ),
    (
        "conflict",
        "甲企业2025年3月收到乙客户单笔货款100万元。",
        [
            ("E1", "财务询问笔录", "询问笔录", "财务称乙客户2025年3月10日单笔转账100万元，交易号TX001。"),
            ("E2", "银行流水", "银行流水", "同一笔TX001交易，2025年3月10日乙客户转账金额实际为80万元。"),
        ],
    ),
    ("no_evidence", "甲企业通过个人账户隐匿销售收入100万元。", []),
    (
        "personal_receipt",
        "加油员个人微信账户收款100万元均属于甲企业2025年3月未申报销售收入。",
        [
            ("E1", "微信收款记录", "微信流水", "加油员个人微信共收到100万元，付款人身份和用途不明。"),
            ("E2", "微信收款截图", "截图", "同一批个人收款记录的截图，共100万元。"),
            ("E3", "个人账户对账单", "对账单", "上述同一批个人微信收款合计100万元，无交易备注。"),
            ("E4", "个人收款汇总", "汇总表", "复制上述微信记录制作的100万元汇总，无企业账簿、销售场景或流向资料。"),
        ],
    ),
]


def build_case(fact, evidence):
    """构造与解析 Skill 相同的字段结构。"""
    return EvidenceReviewInput.model_validate(
        {
            "case_json": {
                "case_summary": {"case_name": "合成测试案件"},
                "violations": [
                    {
                        "violation_id": "V1",
                        "behavior": "销售收入事实审查",
                        "fact_summary": fact,
                        "evidence_ids": [item[0] for item in evidence],
                    }
                ],
                "evidence": [
                    {
                        "evidence_id": item[0],
                        "name": item[1],
                        "type": item[2],
                        "proves": item[3],
                        "related_violation_ids": ["V1"],
                    }
                    for item in evidence
                ],
            }
        }
    )


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("name,fact,evidence", CASES, ids=[item[0] for item in CASES])
async def test_real_model_fact_evidence_cases(name, fact, evidence, tmp_path):
    endpoint = os.getenv("EVIDENCE_REVIEW_PROBE_URL")
    if not endpoint:
        pytest.skip("未配置可选真实模型探针 EVIDENCE_REVIEW_PROBE_URL")
    model = ChatOpenAI(
        base_url=endpoint,
        api_key=os.getenv("EVIDENCE_REVIEW_PROBE_KEY", "unused"),
        model=os.environ["EVIDENCE_REVIEW_PROBE_MODEL"],
        temperature=0,
        timeout=600,
        max_retries=0,
    )
    result = await review_evidence(build_case(fact, evidence), model, None)
    facts = result.violation_reviews[0].fact_reviews
    text = result.model_dump_json()
    (tmp_path / f"{name}.json").write_text(text, encoding="utf-8")
    assert result.summary.violation_count == 1
    assert result.summary.fact_count > 0
    if name == "corroboration":
        assert any(f.conclusion == "sufficient" for f in facts), text
        assert any(len(f.evidence) >= 2 for f in facts), text
    elif name == "single_statement":
        assert all(f.conclusion != "sufficient" for f in facts), text
        assert any(word in text for word in ["孤证", "言词", "单一", "自述"])
        assert any(f.risk_level in {"medium", "high"} for f in facts)
    elif name == "amount_gap":
        assert result.evidence_gaps, text
        assert any(word in text for word in ["20万", "200000", "200,000"]), text
        assert any(f.conclusion in {"doubtful", "insufficient"} for f in facts), text
    elif name == "conflict":
        assert any({c.evidence_a, c.evidence_b} == {"E1", "E2"} for c in result.evidence_conflicts), text
        assert any(f.type == "evidence_conflict" for f in result.review_findings), text
    elif name == "no_evidence":
        assert all(f.conclusion == "insufficient" and f.risk_level == "high" for f in facts)
    elif name == "personal_receipt":
        ownership = [f for f in facts if any(word in f.fact for word in ["企业", "收入", "归属"])]
        assert ownership, text
        assert any(f.conclusion in {"doubtful", "insufficient"} for f in ownership), text
        assert result.evidence_gaps, text
