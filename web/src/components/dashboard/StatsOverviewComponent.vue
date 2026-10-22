<template>
  <div class="stats-overview-container">
    <DashboardMetricGrid>
      <DashboardMetricCard
        :icon="MessageCircle"
        :value="formatNumber(basicStats?.total_conversations)"
        label="累计会话"
        tone="primary"
      >
        <template #meta v-if="basicStats?.conversation_trend">
          <span class="metric-trend" :class="basicStats.conversation_trend > 0 ? 'up' : 'down'">
            <TrendingUp v-if="basicStats.conversation_trend > 0" />
            <TrendingDown v-else />
            {{ Math.abs(basicStats.conversation_trend) }}%
          </span>
        </template>
      </DashboardMetricCard>

      <DashboardMetricCard
        :icon="Activity"
        :value="formatNumber(basicStats?.active_conversations)"
        label="活跃对话"
        tone="success"
      />
      <DashboardMetricCard
        :icon="Mail"
        :value="formatNumber(basicStats?.total_messages)"
        label="总消息数"
        tone="info"
      />
      <DashboardMetricCard
        :icon="Users"
        :value="formatNumber(basicStats?.total_users)"
        label="用户数"
        tone="warning"
      />
      <DashboardMetricCard
        :icon="BarChart3"
        :value="formatNumber(basicStats?.feedback_stats?.total_feedbacks)"
        label="总反馈数"
        tone="accent"
        clickable
        @click="handleFeedbackClick"
      />
      <DashboardMetricCard
        :icon="Heart"
        :value="satisfactionRate == null ? '暂无评价' : `${satisfactionRate}%`"
        label="满意度"
        :tone="getSatisfactionTone()"
      >
        <template #meta>
          <span>评价样本 {{ formatNumber(basicStats?.feedback_stats?.total_feedbacks) }}</span>
        </template>
      </DashboardMetricCard>
    </DashboardMetricGrid>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  MessageCircle,
  Activity,
  Mail,
  Users,
  BarChart3,
  Heart,
  TrendingUp,
  TrendingDown
} from '@lucide/vue'
import { formatNumber } from '@/utils/dashboard'
import DashboardMetricCard from './DashboardMetricCard.vue'
import DashboardMetricGrid from './DashboardMetricGrid.vue'

const props = defineProps({
  basicStats: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['open-feedback'])
const satisfactionRate = computed(() => props.basicStats?.feedback_stats?.satisfaction_rate)

const handleFeedbackClick = () => {
  emit('open-feedback')
}

const getSatisfactionTone = () => {
  const rate = satisfactionRate.value
  if (rate == null) return 'neutral'
  if (rate >= 80) return 'success'
  if (rate >= 60) return 'warning'
  return 'neutral'
}
</script>

<style lang="less" scoped>
.stats-overview-container {
  margin-top: 8px;
}

.dashboard-metric-grid {
  padding: 0 var(--page-padding);
}

.metric-trend {
  display: inline-flex;
  align-items: center;
  gap: 2px;

  svg {
    width: 12px;
    height: 12px;
  }

  &.up {
    color: var(--color-success-700);
  }

  &.down {
    color: var(--color-error-700);
  }
}
</style>
