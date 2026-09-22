import { apiGet, apiAdminPut } from './base'

export const skillNavigationApi = {
  get: (workspace = 'inspection') => apiGet(`/api/system/skill-navigation?workspace=${workspace}`),
  manage: () => apiGet('/api/system/skill-navigation/manage'),
  save: (config) => apiAdminPut('/api/system/skill-navigation', config)
}
