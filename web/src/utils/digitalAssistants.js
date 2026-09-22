import { canVisitPage } from './pageAccess.js'

export const DIGITAL_ASSISTANTS = [
  {
    path: '/chat',
    name: '智能辅助稽查数字人',
    role: '辅助稽查专员',
    description: '协助政策检索、风险核查、案卷整理与稽查报告撰写。',
    image: '/cydx/assistant-cutout.png',
    action: '进入稽查工作区'
  },
  {
    path: '/chat/ducha',
    name: '智能辅助督查数字人',
    role: '辅助督查专员',
    description: '协助督查材料梳理、问题核查与督查工作问答。',
    image: '/cydx/ducha-assistant-cutout.png',
    action: '进入督查工作区'
  }
]

/** 只投影服务端已允许的数字人入口，不产生新的权限。 */
export function availableAssistants(pages) {
  return DIGITAL_ASSISTANTS.filter((assistant) => canVisitPage(pages, assistant.path))
}

/** 多入口供用户选择，单入口直达，其余保留配置首页。 */
export function assistantEntry(access) {
  const choices = availableAssistants(access.pages)
  return choices.length > 1 ? '/choose-assistant' : choices[0]?.path || access.home
}
