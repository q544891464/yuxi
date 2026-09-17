import { apiGet, apiAdminPut } from './base'

export const skillNavigationApi = {
  get: () => apiGet('/api/system/skill-navigation'),
  save: (config) => apiAdminPut('/api/system/skill-navigation', config)
}
