import { apiGet, apiAdminGet, apiAdminPut } from './base'

export const skillNavigationApi = {
  get: () => apiGet('/api/system/skill-navigation'),
  manage: () => apiAdminGet('/api/system/skill-navigation/manage'),
  save: (config) => apiAdminPut('/api/system/skill-navigation', config)
}
