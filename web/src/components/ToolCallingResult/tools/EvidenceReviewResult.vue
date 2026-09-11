<template>
  <section class="evidence-review" aria-label="事实证据审查结果">
    <header>
      <h3>事实证据审查</h3>
      <span class="risk" :class="statusRisk">{{ statusLabel }}</span>
    </header>
    <div class="summary">
      <span
        >违法事项 <strong>{{ result.summary.violation_count }}</strong></span
      >
      <span
        >待证事实 <strong>{{ result.summary.fact_count }}</strong></span
      >
      <span
        >高风险事实 <strong>{{ result.summary.high_risk_count }}</strong></span
      >
      <span
        >证据缺口 <strong>{{ result.evidence_gaps.length }}</strong></span
      >
    </div>
    <p v-if="result.message">{{ result.message }}</p>
    <div v-if="result.limitations.length" class="limitations">
      <p v-for="(item, index) in result.limitations" :key="index">{{ item }}</p>
    </div>
    <article
      v-for="violation in result.violation_reviews"
      :key="violation.violation_id"
      class="violation"
    >
      <h4>{{ violation.violation_name }}</h4>
      <p class="inspection">报告认定：{{ violation.inspection_fact || '未提供具体事实' }}</p>
      <section v-for="fact in violation.fact_reviews" :key="fact.fact_id" class="fact">
        <div class="fact-heading">
          <strong>{{ fact.fact }}</strong>
          <span class="risk" :class="fact.risk_level">{{ riskLabels[fact.risk_level] }}</span>
        </div>
        <p class="conclusion">{{ sufficiencyLabels[fact.conclusion] }}</p>
        <ul v-if="fact.evidence.length" class="evidence-list">
          <li v-for="(item, index) in fact.evidence" :key="`${item.evidence_id}-${index}`">
            <strong>{{ item.name || item.evidence_id }}</strong>
            <span class="relation">{{ relations[item.relation] || item.relation }}</span>
            <p>证明内容：{{ item.proves }}</p>
            <EvidenceReviewSource :reference="item.source_reference" />
          </li>
        </ul>
        <p v-else class="risk high">当前违法事实未关联可识别证据。</p>
        <p>{{ fact.evidence_analysis }}</p>
        <ul v-if="fact.issues.length" class="issues">
          <li v-for="(issue, index) in fact.issues" :key="index">{{ issue }}</li>
        </ul>
        <p v-if="fact.missing_evidence.length">
          <strong>证据缺口：</strong>{{ fact.missing_evidence.join('；') }}
        </p>
        <p v-if="fact.recommendation"><strong>建议：</strong>{{ fact.recommendation }}</p>
        <EvidenceReviewSource :reference="fact.source_reference" />
      </section>
      <p class="overall">事项意见：{{ violation.overall_conclusion }}</p>
    </article>
    <section v-if="result.evidence_conflicts.length" class="findings">
      <h4>证据冲突</h4>
      <div v-for="(item, index) in result.evidence_conflicts" :key="index" class="finding">
        <span class="risk" :class="item.risk_level">{{ riskLabels[item.risk_level] }}</span>
        <strong>{{ item.evidence_a }} / {{ item.evidence_b }}</strong>
        <p>{{ item.conflict }}</p>
        <p>影响：{{ item.impact }}</p>
        <EvidenceReviewSource :reference="item.source_reference" />
      </div>
    </section>
    <section v-if="result.evidence_gaps.length" class="findings">
      <h4>待补材料</h4>
      <div v-for="(item, index) in result.evidence_gaps" :key="index" class="finding">
        <strong>{{ item.fact }}</strong>
        <p>{{ item.missing }}</p>
        <p>影响：{{ item.impact }}</p>
        <p>建议：{{ item.recommendation }}</p>
        <EvidenceReviewSource :reference="item.source_reference" />
      </div>
    </section>
    <section v-if="result.review_findings.length" class="findings">
      <h4>审查发现</h4>
      <div v-for="(item, index) in result.review_findings" :key="index" class="finding">
        <span class="risk" :class="item.risk_level">{{ riskLabels[item.risk_level] }}</span>
        <strong>{{ item.title }}</strong>
        <p>{{ item.description }}</p>
        <p>建议：{{ item.recommendation }}</p>
        <EvidenceReviewSource :reference="item.source_reference" />
      </div>
    </section>
    <p class="scope">本结果仅供事实与证据审查参考，由审理人员复核。</p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import EvidenceReviewSource from './EvidenceReviewSource.vue'
import { riskLabels, sufficiencyLabels } from '@/utils/evidence_review'
const props = defineProps({ result: { type: Object, required: true } })
const statusLabel = computed(
  () =>
    ({ pass: '未发现明显风险', warning: '需关注', risk: '存在高风险' })[props.result.overall_status]
)
const statusRisk = computed(
  () => ({ pass: 'low', warning: 'medium', risk: 'high' })[props.result.overall_status]
)
const relations = {
  direct: '直接证据',
  indirect: '间接证据',
  corroborative: '相互印证',
  supporting: '补强证据',
  duplicate: '重复证据',
  conflicting: '冲突证据'
}
</script>

<style scoped>
.evidence-review {
  color: var(--gray-900);
  font-size: 14px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
header,
.fact-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
}
h3,
h4 {
  margin: 0 0 10px;
}
h3 {
  font-size: 18px;
}
h4 {
  font-size: 16px;
}
p {
  margin: 6px 0;
}
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  padding: 10px 0;
  border-bottom: 1px solid var(--gray-150);
}
.summary strong {
  margin-left: 6px;
}
.risk {
  border-radius: 4px;
  padding: 2px 7px;
  font-size: 12px;
  white-space: normal;
}
.risk.high {
  color: var(--color-error-700);
  background: var(--color-error-50);
}
.risk.medium {
  color: var(--color-warning-700);
  background: var(--color-warning-50);
}
.risk.low {
  color: var(--gray-600);
  background: var(--gray-50);
}
.limitations {
  padding: 8px 12px;
  margin: 12px 0;
  background: var(--gray-50);
  color: var(--gray-600);
  font-size: 12px;
}
.violation,
.findings {
  margin-top: 22px;
}
.inspection,
.relation,
.scope {
  color: var(--gray-600);
}
.fact,
.finding {
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  padding: 14px 16px;
  margin: 12px 0;
  background: var(--gray-0);
}
.finding > .risk {
  margin-right: 8px;
}
.conclusion {
  font-weight: 600;
}
.evidence-list {
  padding-left: 20px;
}
.evidence-list li {
  margin: 10px 0;
}
.relation {
  margin-left: 10px;
  font-size: 12px;
}
.scope {
  font-size: 12px;
  margin-top: 20px;
}
</style>
