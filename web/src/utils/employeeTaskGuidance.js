import {
  getAgentConfigOptionValue,
  getAgentConfigOptions,
  getVisibleAgentResourceSelection
} from './agentConfigUtils.js'

const profiles = {
  'default-chatbot': {
    purpose: '整理已有材料，提炼要点和下一步行动。',
    examples: [
      {
        id: 'summarize',
        title: '提炼材料要点',
        material: '粘贴一段通知、说明或会议记录。',
        result: '一段摘要、关键事项和待确认问题。',
        prompt:
          '请仅根据以下材料，整理：\n1. 一段简明摘要\n2. 关键事项（保留原文中的时间、数字和条件）\n3. 需要进一步确认的问题\n材料没有说明的内容请标为“材料未说明”，不要补写事实。\n\n材料：\n[在这里粘贴材料]'
      },
      {
        id: 'actions',
        title: '整理行动清单',
        material: '粘贴讨论记录或待办说明。',
        result: '包含事项、负责人、时间和待确认项的清单。',
        prompt:
          '请将以下记录整理成行动清单，按“事项、负责人、截止时间、待确认问题”列成表格。只提取材料中明确的信息；未指定的负责人和时间写“待确认”，不要代为安排。\n\n记录：\n[在这里粘贴记录]'
      }
    ]
  },
  'deep-research': {
    purpose: '明确研究问题，梳理材料中的依据与差异。',
    examples: [
      {
        id: 'research-plan',
        title: '制定研究计划',
        material: '填写研究主题、使用目的和已有线索。',
        result: '研究问题、分析维度和待补充材料清单。',
        prompt:
          '请先为以下主题制定研究计划，暂不联网检索，也不要编写尚未验证的研究结论。请给出研究范围、需回答的问题、分析维度及待补充材料；信息不足时先列出澄清问题。结果直接在对话中呈现。\n\n研究主题：[填写主题]\n使用目的：[填写用途]\n已有线索：[粘贴线索或写“暂无”]'
      },
      {
        id: 'compare',
        title: '对比两份材料',
        material: '粘贴材料 A、材料 B，并说明对比目的。',
        result: '异同对照、原文依据和仍需核实的问题。',
        prompt:
          '请只依据下面两份材料进行对比，暂不联网检索。先说明可比较的维度，再列出相同点、差异和各自的原文依据（标注材料 A 或 B），最后列出材料不足、冲突或需要核实的问题。不要把材料中的主张当作已证实事实；结果直接在对话中呈现。\n\n对比目的：[填写目的]\n材料 A：\n[粘贴材料 A]\n\n材料 B：\n[粘贴材料 B]'
      }
    ]
  }
}

/** 广场只说明经服务端核对的角色用途，自建员工沿用自己的描述。 */
export function employeeTaskPurpose(agent) {
  return (
    profiles[agent?.starter_task_profile]?.purpose ||
    agent?.description ||
    '描述任务目标和已有材料，开始新的对话。'
  )
}

/** 示例依赖取员工启用资源与当前账号可访问选项的交集。 */
export function getEmployeeTaskGuide(agent, config, items) {
  const empty = (notice) => ({ examples: [], notice })
  if (!agent) return empty('请先从数字员工广场选择一个可用员工。')
  const profile = profiles[agent.starter_task_profile]
  if (!profile)
    return empty(
      ['default-chatbot', 'deep-research'].includes(agent.slug)
        ? '该员工配置已调整或尚未核对，暂不展示预置示例。请按员工说明描述任务，或联系管理员核对配置。'
        : '先说明任务目标，再粘贴相关材料，并写明希望得到的结果。'
    )
  if (!items || !config) return empty('正在核对员工配置，请稍候。')
  const savedPrompt = agent.config_json?.context?.system_prompt ?? items.system_prompt?.default
  if (config.system_prompt !== undefined && config.system_prompt !== savedPrompt)
    return empty('员工角色说明已调整，请先保存并重新核对配置。')
  if (agent.starter_task_profile === 'deep-research') {
    const required = {
      skills: ['deep-research'],
      subagents: ['research-explorer', 'fact-verifier']
    }
    for (const [field, ids] of Object.entries(required)) {
      const available = getAgentConfigOptions(items[field]).map(getAgentConfigOptionValue)
      const selected = getVisibleAgentResourceSelection(config[field], items[field], available)
      if (!ids.every((id) => selected.includes(id)))
        return empty(
          '研究所需的技能或协作员工未启用、不可访问或尚未加载。请联系管理员核对，或先描述你的研究目标。'
        )
    }
  }
  return {
    examples: profile.examples,
    notice: '示例使用你粘贴的文字，结果在对话中呈现。填写后由你点击发送。'
  }
}
