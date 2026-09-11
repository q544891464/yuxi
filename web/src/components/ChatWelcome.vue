<template>
  <section class="chat-welcome" aria-label="智能辅助审理数字人欢迎页">
    <div class="welcome-hero">
      <div class="assistant-portrait" role="img" aria-label="智能辅助审理数字人形象"></div>
      <div class="welcome-copy">
        <span class="welcome-eyebrow">专业 · 规范 · 智能 · 高效</span>
        <h1>您好！</h1>
        <div class="welcome-rule"></div>
        <p>我是您的智能辅助审理数字人，<br />请问需要协助什么？</p>
      </div>
      <span class="welcome-motto">以数治税<br />以智助查</span>
    </div>
    <div class="welcome-role">
      <div class="role-symbol"><ShieldCheck :size="30" /></div>
      <div>
        <h2>税务稽查辅助专员</h2>
        <p>协助政策检索、风险核查、案卷整理与流程问答</p>
      </div>
      <span class="role-note">依法稽查 · 精准高效</span>
    </div>
    <section class="skill-entry" aria-label="审理技能">
      <div class="skill-entry-copy">
        <span class="skill-entry-tag">报告解析</span>
        <h2>稽查报告结构化解析</h2>
        <p>提取案件信息、违法事实、证据和税费数据，保留原文出处，标记缺失与冲突。</p>
        <small>上传 Word、PDF 或粘贴报告正文后发送，不作最终审理结论。</small>
        <small v-if="!reportParserAvailable" role="status">当前智能体尚未启用此技能</small>
      </div>
      <button type="button" :disabled="!reportParserAvailable" @click="useReportParser">
        使用技能<ChevronRight :size="18" />
      </button>
    </section>
    <div class="welcome-questions" aria-label="建议问题">
      <button
        v-for="question in questions"
        :key="question"
        type="button"
        @click="$emit('prompt', question)"
      >
        {{ question }}<ChevronRight :size="16" />
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { ChevronRight, ShieldCheck } from '@lucide/vue'
import { formatMentionToken } from '@/utils/mention_token'
const props = defineProps({ skills: { type: Array, default: () => [] } })
const emit = defineEmits(['prompt'])
const reportParserSlug = 'tax-inspection-report-parser'
const reportParserAvailable = computed(() =>
  props.skills.some((skill) => skill.slug === reportParserSlug)
)

// 使用当前智能体允许的技能引用，保留用户上传材料和确认发送的步骤。
const useReportParser = () => {
  if (!reportParserAvailable.value) return
  emit(
    'prompt',
    `${formatMentionToken('skill', reportParserSlug)} 请解析我提供的税务稽查报告，输出案件摘要、结构化 JSON、原文溯源、异常和缺失项；如尚未提供报告，请先提示我上传或粘贴正文。`
  )
}
const questions = [
  '企业涉税风险如何初筛？',
  '发票异常如何核查？',
  '如何准备稽查询问清单？',
  '如何整理稽查案卷材料？'
]
</script>

<style scoped>
.chat-welcome {
  text-align: left;
  color: #112452;
}
.welcome-hero {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 280px;
  margin-top: 40px;
  border: 1px solid white;
  border-radius: 26px;
  overflow: visible;
  background: linear-gradient(135deg, #d9eaff, #f6fbff 65%, #deedff);
}
.welcome-hero::after {
  content: '';
  position: absolute;
  width: 60%;
  height: 100px;
  right: 0;
  bottom: 0;
  border-radius: 100% 0 26px 0;
  background: #bddbff66;
  pointer-events: none;
}
.assistant-portrait {
  flex: 0 0 268px;
  height: 320px;
  margin: -40px 24px 0 16px;
  align-self: flex-end;
  background: url('/cydx/assistant-sheet.png') no-repeat -5px -36px / 557px 417.75px;
  clip-path: polygon(0 0, 72% 0, 72% 45%, 100% 45%, 100% 70%, 88% 100%, 0 100%);
  mix-blend-mode: multiply;
}

.welcome-copy {
  position: relative;
  z-index: 1;
  padding: 16px 0;
}
.welcome-eyebrow {
  color: #5572a0;
  font-size: 12px;
  letter-spacing: 3px;
}
.welcome-copy h1 {
  font-size: clamp(30px, 3.5vw, 40px);
  color: #101e47;
  margin: 10px 0;
  font-weight: 750;
}
.welcome-rule {
  width: 46px;
  height: 4px;
  border-radius: 4px;
  background: #1765ff;
  margin: 10px 0 12px;
}
.welcome-copy p {
  font-size: clamp(16px, 1.7vw, 20px);
  line-height: 1.7;
  margin: 0;
}
.welcome-motto {
  margin-left: auto;
  padding: 24px;
  font-size: 23px;
  line-height: 1.8;
  color: #799de4;
  font-style: italic;
  white-space: nowrap;
  transform: rotate(-8deg);
}
.welcome-role {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 24px;
  margin: 14px 0;
  background: #ffffffbf;
  border: 1px solid #fff;
  border-radius: 22px;
}
.role-symbol {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  background: #e7f0ff;
  color: #1765ff;
  border-radius: 50%;
}
.welcome-role h2 {
  color: #145bf1;
  margin: 0 0 5px;
  font-size: 19px;
}
.welcome-role p {
  margin: 0;
  font-size: 13px;
  color: #60759a;
}
.role-note {
  margin-left: auto;
  color: #7d96bb;
  font-size: 13px;
  white-space: nowrap;
}
.skill-entry {
  display: flex;
  align-items: center;
  gap: 24px;
  margin: 16px 0;
  padding: 22px 24px;
  border: 1px solid #d5e5ff;
  border-radius: 22px;
  background: #ffffffd9;
}
.skill-entry-copy {
  flex: 1;
}
.skill-entry-tag {
  color: #1765ff;
  font-size: 12px;
}
.skill-entry h2 {
  margin: 6px 0 8px;
  font-size: 20px;
  color: #112452;
}
.skill-entry p {
  margin: 0 0 8px;
  font-size: 14px;
  color: #526c96;
}
.skill-entry small {
  display: block;
  color: #6f82a0;
  line-height: 1.7;
}
.skill-entry button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  border: 0;
  border-radius: 12px;
  background: #1765ff;
  color: white;
  cursor: pointer;
  white-space: nowrap;
}
.skill-entry button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.skill-entry button:focus-visible {
  outline: 2px solid #1765ff;
  outline-offset: 4px;
}
.welcome-questions {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}
.welcome-questions button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid #e3edff;
  border-radius: 30px;
  background: #ffffffd9;
  color: #385681;
  cursor: pointer;
  text-align: left;
  font-size: 12px;
  box-shadow: 0 3px 12px #326cc008;
}
.welcome-questions button:hover {
  border-color: #1765ff;
  color: #1765ff;
}
.welcome-questions button:focus-visible {
  outline: 2px solid #1765ff;
  outline-offset: 3px;
}
@media (max-width: 1100px) {
  .welcome-motto,
  .role-note {
    display: none;
  }
  .assistant-portrait {
    flex-basis: 268px;
  }
}
@media (max-width: 640px) {
  .welcome-hero {
    min-height: 180px;
  }
  .assistant-portrait {
    flex-basis: 130px;
    height: 140px;
    background-size: 245px 183.75px;
    background-position: -2px -16px;
    margin: 0 8px 0 0;
  }
  .welcome-eyebrow {
    display: none;
  }
  .welcome-copy {
    padding: 18px 10px;
  }
  .welcome-copy h1 {
    font-size: 30px;
  }
  .welcome-copy p {
    font-size: 14px;
  }
  .welcome-rule {
    margin: 8px 0 12px;
  }
  .welcome-role {
    padding: 12px;
    gap: 10px;
  }
  .welcome-role h2 {
    font-size: 16px;
  }
  .welcome-role p {
    font-size: 12px;
  }
  .role-symbol {
    width: 40px;
    height: 40px;
  }
  .welcome-questions {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
}
</style>
