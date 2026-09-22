import { apiGet, apiSuperAdminGet, apiSuperAdminPut } from './base'

export const pageAccessApi = {
  resolve: (path) => apiGet(`/api/system/page-access?path=${encodeURIComponent(path)}`),
  manage: () => apiSuperAdminGet('/api/system/page-access/manage'),
  save: (config) => apiSuperAdminPut('/api/system/page-access', config)
}
