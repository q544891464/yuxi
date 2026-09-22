import { apiGet, apiPost, apiPut, apiRequest, buildQuery } from './base'

const root = '/api/formal-documents'
export const formalDocumentApi = {
  workflows: (manage = false) => apiGet(`${root}/workflows?manage=${manage}`),
  saveWorkflows: (config) => apiPut(`${root}/workflows`, config),
  list: (params) => apiGet(`${root}?${buildQuery(params)}`),
  create: (data) => apiPost(root, data),
  detail: (id) => apiGet(`${root}/${encodeURIComponent(id)}`),
  act: (id, data) => apiPost(`${root}/${encodeURIComponent(id)}/actions`, data),
  upload: (id, revision, file, options = {}) => {
    const body = new FormData()
    body.append('revision', revision)
    body.append('file', file)
    return apiRequest(`${root}/${encodeURIComponent(id)}/files`, {
      method: 'POST',
      body,
      ...options
    })
  },
  download: (id, fileId) =>
    apiGet(
      `${root}/${encodeURIComponent(id)}/files/${encodeURIComponent(fileId)}`,
      {},
      true,
      'blob'
    )
}
