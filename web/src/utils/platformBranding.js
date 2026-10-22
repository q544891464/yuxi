export const PLATFORM_NAME = '智能数字员工平台'

const LEGACY_PLATFORM_NAMES = new Set(['Yuxi', 'Yuxi 智能助手'])

/** 将历史默认品牌名称转换为当前平台名称。 */
export function normalizePlatformName(value, fallback = PLATFORM_NAME) {
  const name = typeof value === 'string' ? value.trim() : ''
  return !name || LEGACY_PLATFORM_NAMES.has(name) ? fallback : name
}

/** 归一化旧部署返回的默认品牌字段，保留管理员配置的自定义品牌。 */
export function normalizePlatformBranding(info = {}) {
  const organization = info.organization || {}
  const branding = info.branding || {}

  return {
    ...info,
    organization: {
      ...organization,
      name: normalizePlatformName(organization.name)
    },
    branding: {
      ...branding,
      name: normalizePlatformName(branding.name),
      title: normalizePlatformName(branding.title)
    }
  }
}
