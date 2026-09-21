<template>
  <section
    class="chat-welcome"
    :class="{ 'skill-selected': skillSelected }"
    :aria-label="`智能辅助${ducha ? '督查' : '稽查'}数字人欢迎页`"
  >
    <div class="welcome-hero">
      <div
        class="assistant-portrait"
        role="img"
        :aria-label="`智能辅助${ducha ? '督查' : '稽查'}数字人形象`"
      ></div>
      <div class="welcome-copy">
        <span class="welcome-eyebrow">专业 · 规范 · 智能 · 高效</span>
        <h1>您好！</h1>
        <div class="welcome-rule"></div>
        <p>我是您的智能辅助{{ ducha ? '督查' : '稽查' }}数字人，<br />请问需要协助什么？</p>
      </div>
      <span class="welcome-motto">以数治税<br />以智助查</span>
    </div>
    <div class="welcome-role">
      <div class="role-symbol"><ShieldCheck :size="30" /></div>
      <div class="role-description">
        <h2>辅助{{ ducha ? '督查' : '稽查' }}专员</h2>
        <p>协助政策检索、风险核查、案卷整理与流程问答</p>
      </div>
      <dl v-if="!ducha" class="resource-stats" aria-label="当前可访问资源" :aria-busy="loading">
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
    <slot name="skill-description"></slot>
    <div v-if="!ducha && !loading && loadFailed" class="welcome-data-note" role="status">
      部分资源暂未加载 <button type="button" @click="loadResources">重试</button>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ShieldCheck, Files, Bot, Sparkles } from '@lucide/vue'
import { databaseApi } from '@/apis/knowledge_api'
import { agentApi } from '@/apis/agent_api'
import { listAccessibleSkills } from '@/apis/skill_api'
import { summarizeChatWelcome } from '@/utils/chatWelcome'

const props = defineProps({ skillSelected: Boolean, ducha: Boolean })

const loading = ref(true)
const summary = ref({ questions: [], fileCount: null, subagentCount: null, skillCount: null })
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
onMounted(() => {
  if (!props.ducha) loadResources()
})
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
  min-height: clamp(164px, 23vh, 230px);
  margin-top: 24px;
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
  flex: 0 0 clamp(170px, 20vw, 240px);
  height: clamp(188px, calc(23vh + 24px), 254px);
  margin: -24px 24px 0 16px;
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
  font-size: clamp(28px, 2.4vw, 36px);
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
  font-size: clamp(15px, 1.25vw, 18px);
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
  padding: 12px 20px;
  margin: 12px 0;
  background: #ffffffbf;
  border: 1px solid #fff;
  border-radius: 22px;
}
.role-symbol {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  background: #e7f0ff;
  color: #1765ff;
  border-radius: 50%;
}
.welcome-role h2 {
  color: #145bf1;
  margin: 0 0 5px;
  font-size: 17px;
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
  margin: 0 0 4px;
  font-size: 24px;
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
@media (max-width: 1280px) {
  .welcome-motto {
    display: none;
  }
  .resource-stats > div {
    min-width: 82px;
    padding-inline: 10px;
  }
}
@media (max-height: 760px) and (min-width: 761px) {
  .welcome-hero {
    min-height: 140px;
  }
  .assistant-portrait {
    height: 164px;
    flex-basis: 160px;
  }
  .welcome-copy {
    padding: 8px 0;
  }
  .welcome-copy h1 {
    margin: 4px 0;
    font-size: 28px;
  }
  .welcome-rule {
    margin: 6px 0;
  }
  .welcome-eyebrow {
    font-size: 11px;
  }
  .welcome-role {
    padding-block: 10px;
  }
}
@media (max-width: 900px) {
  .welcome-role {
    flex-wrap: wrap;
  }
  .resource-stats {
    width: 100%;
    justify-content: space-around;
  }
  .resource-stats > div {
    flex: 1;
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
}
</style>
