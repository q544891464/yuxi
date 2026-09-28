<template>
  <section
    class="chat-welcome"
    aria-label="Yuxi 智能助手欢迎页"
  >
    <div class="welcome-hero">
      <div class="welcome-copy">
        <span class="welcome-eyebrow">Yuxi · 知识与智能体工作台</span>
        <h1>您好，欢迎使用 Yuxi</h1>
        <div class="welcome-rule"></div>
        <p>可以直接提问，或引用文件、知识库和技能开始工作。</p>
      </div>
    </div>
    <div class="welcome-role">
      <div class="role-symbol"><ShieldCheck :size="30" /></div>
      <div class="role-description">
        <h2>智能助手</h2>
        <p>支持资料检索、文件处理和多智能体协作</p>
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
    <div v-if="!loading && loadFailed" class="welcome-data-note" role="status">
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
  loadResources()
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
  padding: 22px clamp(24px, 5vw, 64px);
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
  .resource-stats > div {
    min-width: 82px;
    padding-inline: 10px;
  }
}
@media (max-height: 760px) and (min-width: 761px) {
  .welcome-hero {
    min-height: 140px;
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
