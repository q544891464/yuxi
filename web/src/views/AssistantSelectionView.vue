<template>
  <div class="assistant-selection">
    <header class="selection-header">
      <div class="selection-brand">
        <img src="/cydx/ai-logo.png" alt="" width="44" height="44" />
        <div><strong>智能辅助工作平台</strong><span>专业 · 规范 · 智能 · 高效</span></div>
      </div>
      <button class="switch-account" type="button" @click="switchAccount">
        <LogOut :size="16" />切换账号
      </button>
    </header>
    <main class="selection-main">
      <div class="selection-heading">
        <p class="selection-eyebrow">工作入口</p>
        <h1>请选择您的数字人</h1>
        <p>根据本次工作任务，选择一位数字人开始协作。</p>
      </div>
      <nav class="assistant-cards" aria-label="可访问的数字人">
        <RouterLink
          v-for="assistant in choices"
          :key="assistant.path"
          :to="assistant.path"
          class="assistant-card"
        >
          <div class="portrait-stage"><img :src="assistant.image" alt="" draggable="false" /></div>
          <div class="card-copy">
            <span class="assistant-role">{{ assistant.role }}</span>
            <h2>{{ assistant.name }}</h2>
            <p>{{ assistant.description }}</p>
            <span class="enter-workspace">{{ assistant.action }}<ArrowRight :size="18" /></span>
          </div>
        </RouterLink>
      </nav>
      <p class="selection-note"><ShieldCheck :size="15" />仅展示您有权限使用的数字人</p>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, LogOut, ShieldCheck } from '@lucide/vue'
import { useUserStore } from '@/stores/user'
import { availableAssistants } from '@/utils/digitalAssistants'
const userStore = useUserStore()
const router = useRouter()
const choices = computed(() => availableAssistants(userStore.allowedPages))
const switchAccount = () => {
  userStore.logout()
  router.replace('/login')
}
</script>

<style scoped>
.assistant-selection {
  min-height: 100dvh;
  background: var(--consumer-page-background);
  color: var(--consumer-brand-color);
}
.selection-header {
  min-height: 76px;
  padding: 12px clamp(20px, 4vw, 56px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: var(--consumer-header-background);
}
.selection-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.selection-brand img {
  object-fit: contain;
}
.selection-brand strong {
  display: block;
  font-size: 20px;
}
.selection-brand span {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--consumer-muted-color);
}
.switch-account {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex-shrink: 0;
  background: transparent;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 9px 12px;
  color: var(--gray-700);
  cursor: pointer;
}
.selection-main {
  width: min(960px, calc(100% - 48px));
  margin: 0 auto;
  padding: 28px 0 20px;
}
.selection-heading {
  text-align: center;
  margin-bottom: 24px;
}
.selection-eyebrow {
  color: var(--main-600);
  font-size: 12px;
  letter-spacing: 3px;
  margin: 0 0 6px;
}
h1 {
  font-size: clamp(24px, 3vw, 32px);
  margin: 0 0 8px;
  font-weight: 700;
}
.selection-heading > p:last-child {
  color: var(--consumer-muted-color);
  margin: 0;
}
.assistant-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
}
.assistant-card {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-decoration: none;
  color: inherit;
  background: var(--consumer-header-background);
  border: 1px solid var(--gray-200);
  border-radius: 24px;
  box-shadow: 0 8px 24px var(--shadow-1);
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}
.assistant-card:hover {
  border-color: var(--main-400);
  box-shadow: 0 8px 24px var(--shadow-2);
}
.assistant-card:focus-visible,
.switch-account:focus-visible {
  outline: 3px solid var(--main-400);
  outline-offset: 4px;
}
.portrait-stage {
  height: clamp(180px, 28vh, 270px);
  background: var(--consumer-page-background);
  padding: 12px 24px 0;
}
.portrait-stage img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center bottom;
  pointer-events: none;
}
.card-copy {
  padding: 20px 26px 24px;
}
.assistant-role {
  font-size: 12px;
  color: var(--main-600);
}
h2 {
  font-size: clamp(18px, 2vw, 23px);
  margin: 6px 0 10px;
  color: var(--consumer-brand-color);
}
.card-copy p {
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-600);
  margin: 0 0 18px;
  min-height: 48px;
}
.enter-workspace {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--main-700);
  background: var(--main-50);
  padding: 12px 16px;
  border-radius: 10px;
  font-weight: 600;
}
.selection-note {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  margin: 18px 0 0;
  font-size: 12px;
  color: var(--consumer-muted-color);
}
@media (min-height: 900px) {
  .selection-main {
    padding-top: 64px;
  }
  .selection-heading {
    margin-bottom: 36px;
  }
}
@media (max-width: 640px) {
  .selection-header {
    padding: 12px 16px;
  }
  .selection-brand strong {
    font-size: 16px;
  }
  .selection-brand img {
    width: 34px;
    height: 34px;
  }
  .switch-account {
    font-size: 12px;
    padding: 8px;
  }
  .selection-main {
    width: calc(100% - 32px);
    padding-top: 24px;
  }
  .assistant-cards {
    grid-template-columns: 1fr;
    gap: 18px;
  }
  .portrait-stage {
    height: 200px;
  }
  .card-copy {
    padding: 18px 22px;
  }
  .card-copy p {
    min-height: 0;
  }
}
</style>
