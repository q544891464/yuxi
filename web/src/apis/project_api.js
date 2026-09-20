import { apiDelete, apiGet, apiPost, apiPut, buildQuery } from './base'

export const projectApi = {
  getProjects: (status = 'active') =>
    apiGet(status === 'active' ? '/api/projects' : `/api/projects?${buildQuery({ status })}`),

  createProject: ({ requestId, name, mode, path = null }) =>
    apiPost('/api/projects', {
      request_id: requestId,
      name,
      workdir: {
        mode,
        ...(mode === 'linked' && path ? { path: String(path).replace(/^\/+/, '') } : {})
      }
    }),

  renameProject: (projectId, name) => apiPut(`/api/projects/${projectId}`, { name }),

  deleteProject: (projectId) => apiDelete(`/api/projects/${projectId}`),

  archiveProject: (projectId) => apiPost(`/api/projects/${projectId}/archive`, {}),

  restoreProject: (projectId) => apiPost(`/api/projects/${projectId}/restore`, {}),

  getHistoryCandidates: ({ query = '', limit = 20, offset = 0 } = {}) =>
    apiGet(`/api/projects/history-candidates?${buildQuery({ q: query, limit, offset })}`)
}
