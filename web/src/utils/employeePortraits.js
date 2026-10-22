export const DEFAULT_EMPLOYEE_PORTRAITS = [
  { name: '智能助理', src: '/employees/assistant.png' },
  { name: '研究专员', src: '/employees/researcher.png' },
  { name: '协作专员', src: '/employees/coordinator.png' }
]

/** 为未上传形象的数字员工提供随应用发布的默认人物。 */
export function getDefaultEmployeePortrait(agent) {
  const key = agent?.slug || agent?.id || ''
  if (key === 'deep-research') return DEFAULT_EMPLOYEE_PORTRAITS[1].src
  if (!key || key === 'default-chatbot') return DEFAULT_EMPLOYEE_PORTRAITS[0].src
  return DEFAULT_EMPLOYEE_PORTRAITS[2].src
}
