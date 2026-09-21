import { apiGet, apiAdminPut } from './base'

export const skillNavigationApi = {
  get: () => apiGet('/api/system/skill-navigation'),
  manage: () => apiGet('/api/system/skill-navigation/manage'),
  save: (config) => apiAdminPut('/api/system/skill-navigation', config)
}
