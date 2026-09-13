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
      <div class="role-description">
        <h2>税务审理辅助专员</h2>
        <p>协助政策检索、风险核查、案卷整理与流程问答</p>
      </div>
      <dl class="resource-stats" aria-label="当前可访问资源" :aria-busy="loading">
        <div
          v-for="stat in stats"
          :key="stat.label"
          :title="stat.value === null ? '暂未获取' : '当前用户可访问的数量'"
        >
          <dd>{{ stat.value === null ? '—' : stat.value.toLocaleString('zh-CN') }}</dd>
          <dt><component :is="stat.icon" :size="16" />{{ stat.label }}</dt>
        </div>
      </dl>
    </div>
    <div v-if="questions.length" class="welcome-questions" aria-label="知识库示例问题">
      <button
        v-for="question in questions"
        :key="question"
        type="button"
        @click="$emit('prompt', question)"
      >
        {{ question }}<ChevronRight :size="16" />
      </button>
    </div>
    <div v-if="!loading && loadFailed" class="welcome-data-note" role="status">
      部分资源暂未加载 <button type="button" @click="loadResources">重试</button>
    </div>
    <p v-else-if="!loading && !questions.length" class="welcome-data-note">
      知识库暂无预置问题，您可以直接输入问题。
    </p>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ChevronRight, ShieldCheck, Files, Bot, Sparkles } from '@lucide/vue'
import { databaseApi } from '@/apis/knowledge_api'
import { agentApi } from '@/apis/agent_api'
import { listAccessibleSkills } from '@/apis/skill_api'
import { summarizeChatWelcome } from '@/utils/chatWelcome'

defineEmits(['prompt'])
const loading = ref(true)
const summary = ref({ questions: [], fileCount: null, subagentCount: null, skillCount: null })
const questions = computed(() => summary.value.questions)
const stats = computed(() => [
  { label: '知识库文件', value: summary.value.fileCount, icon: Files },
  { label: '子智能体', value: summary.value.subagentCount, icon: Bot },
  { label: 'Skills', value: summary.value.skillCount, icon: Sparkles }
])
const loadFailed = computed(() => stats.value.some((stat) => stat.value === null))

/** 进入新对话时读取当前用户可访问的资源快照。 */
async function loadResources() {
  loading.value = true
  try {
    summary.value = summarizeChatWelcome(
      await Promise.allSettled([
        databaseApi.getAccessibleDatabases(),
        agentApi.getAgents({ includeSubagents: true }),
        listAccessibleSkills()
      ])
    )
  } finally {
    loading.value = false
  }
}
onMounted(loadResources)
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
  flex: 0 0 306px;
  height: 320px;
  margin: -40px 24px 0 16px;
  align-self: flex-end;
  background: url('/cydx/assistant-cutout.png') center bottom / contain no-repeat;
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
.role-description {
  min-width: 0;
}
.resource-stats {
  display: flex;
  margin: 0 0 0 auto;
  flex-shrink: 0;
  color: #145bf1;
}
.resource-stats > div {
  min-width: 110px;
  padding: 4px 18px;
  border-left: 1px solid #e3edff;
  text-align: center;
}
.resource-stats dd {
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 750;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
}
.resource-stats dt {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #385681;
  font-size: 12px;
  white-space: nowrap;
}
.welcome-data-note {
  margin: 10px 0 0;
  font-size: 12px;
  color: #60759a;
}
.welcome-data-note button {
  border: 0;
  background: transparent;
  color: #145bf1;
  cursor: pointer;
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
  min-height: 52px;
  line-height: 1.5;
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
  .welcome-motto {
    display: none;
  }
  .resource-stats > div {
    min-width: 90px;
    padding-inline: 10px;
  }
  .assistant-portrait {
    flex-basis: 306px;
  }
}
@media (max-height: 850px) and (min-width: 1000px) {
  .welcome-hero {
    min-height: 180px;
    margin-top: 24px;
  }
  .assistant-portrait {
    flex-basis: 195px;
    height: 204px;
    margin-top: -24px;
  }
  .welcome-copy {
    padding: 8px 0;
  }
  .welcome-copy h1 {
    font-size: 32px;
    margin: 6px 0;
  }
  .welcome-copy p {
    font-size: 17px;
  }
  .welcome-role {
    padding: 12px 18px;
  }
}
@media (max-width: 640px) {
  .welcome-hero {
    min-height: 180px;
  }
  .assistant-portrait {
    flex-basis: 130px;
    height: 140px;
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
