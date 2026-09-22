import { useUserStore, checkAdminPermission, checkSuperAdminPermission } from '@/stores/user'
import { message } from 'ant-design-vue'

function safeRequestMetadata(url, requestOptions, response = null) {
  let path = '[invalid-url]'
  try {
    path = new URL(url, 'http://yuxi.local').pathname
  } catch {
    // 不把无法解析的原始 URL 写入日志，其中可能包含凭据或其他敏感查询参数。
  }

  return {
    path,
    method: requestOptions?.method || 'GET',
    ...(response
      ? {
          status: response.status
        }
      : {})
  }
}

const SAFE_ERROR_RESPONSE_HEADERS = ['x-lock-remaining', 'retry-after', 'www-authenticate']

/**
 * 统一构建查询参数，保留 0 和 false，省略空值。
 */
export const buildQuery = (params) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value))
    }
  })
  return query.toString()
}

function safeResponseHeaders(headers) {
  const safeHeaders = new Headers()
  for (const name of SAFE_ERROR_RESPONSE_HEADERS) {
    const value = headers.get(name)
    if (value !== null) safeHeaders.set(name, value)
  }
  return safeHeaders
}

function safeErrorData(errorData, status, publicMessage) {
  if (status !== 422) return { detail: publicMessage }
  const detail = errorData?.detail
  if (!Array.isArray(detail)) return { detail: publicMessage }
  return {
    detail: detail.map((item) => ({
      loc: Array.isArray(item?.loc) ? item.loc.map((part) => String(part)) : [],
      msg: '请求参数验证失败',
      type: typeof item?.type === 'string' ? item.type : 'validation_error'
    }))
  }
}

const SKILL_ERROR_MESSAGES = Object.freeze({
  skill_not_accessible: '技能或文件不存在，或当前账号没有访问权限，请刷新列表并联系管理员确认。',
  skill_invalid_request: '技能操作未完成，请检查导入文件、填写内容和所选技能后重试。',
  skill_upload_format: '请上传 ZIP 技能包或名为 SKILL.md 的说明文件。',
  skill_manifest_missing: '技能包缺少 SKILL.md，请补齐说明文件后重新导入。',
  skill_name_missing: 'SKILL.md 缺少 name，请填写技能名称后重新导入。',
  skill_description_missing: 'SKILL.md 缺少 description，请补充技能用途说明。',
  skill_manifest_invalid: 'SKILL.md 的 YAML 配置格式不正确，请检查顶部 --- 包围的配置内容。',
  skill_draft_expired: '本次导入已过期，请重新选择文件并导入。',
  skill_name_conflict: '技能标识已被占用，请选择更新原技能，或修改标识后重新导入。',
  skill_slug_mismatch: '技能目录名和说明文件中的 slug 不一致，请统一后重新导入。',
  skill_slug_invalid: '技能 slug 请使用小写字母、数字和短横线，长度不超过 128。',
  skill_selection_required: '请先选择需要安装的技能。',
  skill_archive_layout: 'ZIP 中必须包含一个技能的 SKILL.md，请将多个技能分开导入。'
})

function publicErrorMessage(url, status, headers, requiresAuth, errorData) {
  const path = safeRequestMetadata(url, {}).path
  const code = errorData?.detail?.code
  if (
    [400, 404, 409, 422].includes(status) &&
    /^\/api\/(system\/)?skills(?:\/|$)/.test(path) &&
    typeof code === 'string' &&
    Object.hasOwn(SKILL_ERROR_MESSAGES, code)
  )
    return SKILL_ERROR_MESSAGES[code]
  if (status === 400) return '提交内容不符合要求，请检查填写内容或上传文件后重试。'
  if (status === 401) {
    if (requiresAuth) return '登录已过期，请重新登录'
    return path === '/api/auth/token' ? '用户名或密码错误' : '认证请求失败'
  }
  if (status === 403) return '没有权限执行此操作'
  if (status === 404) return '请求资源不存在'
  if (status === 409) return '请求冲突，请刷新后重试'
  if (status === 410) return '请求已失效'
  if (status === 413) return '文件或提交内容超过大小限制，请缩小文件后重试。'
  if (status === 422) return '提交信息不完整或格式不正确，请检查必填项后重试。'
  if (status === 423) {
    const remaining = Number.parseInt(headers.get('x-lock-remaining') || '', 10)
    return Number.isSafeInteger(remaining) && remaining > 0
      ? `账户已锁定 ${remaining} 秒`
      : '账户已锁定，请稍后再试'
  }
  if (status === 429) return '请求过于频繁，请稍后重试'
  if (status >= 500) return '服务暂时无法完成操作，请稍后重试；若持续失败，请联系管理员。'
  return `请求失败: ${status}`
}

/**
 * 基础API请求封装
 * 提供统一的请求方法，自动处理认证头和错误
 */

/**
 * 发送API请求的基础函数
 * @param {string} url - API端点
 * @param {Object} options - 请求选项
 * @param {boolean} requiresAuth - 是否需要认证头
 * @param {string} responseType - 响应类型: 'json' | 'text' | 'blob'
 * @returns {Promise} - 请求结果
 */
export async function apiRequest(url, options = {}, requiresAuth = true, responseType = 'json') {
  try {
    const isFormData = options?.body instanceof FormData
    // 默认请求配置
    const requestOptions = {
      ...options,
      headers: {
        ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers
      }
    }

    // 如果需要认证，添加认证头
    if (requiresAuth) {
      const userStore = useUserStore()
      if (!userStore.isLoggedIn) {
        throw new Error('用户未登录')
      }

      Object.assign(requestOptions.headers, userStore.getAuthHeaders())
    }

    // 发送请求
    const response = await fetch(url, requestOptions)

    // 处理API返回的错误
    if (!response.ok) {
      // 尝试解析错误信息
      let errorData = null

      console.error('API请求失败:', safeRequestMetadata(url, requestOptions, response))

      try {
        errorData = await response.json()
        // 422 常由请求校验失败引起。只记录不可逆的请求元数据；认证头、请求体与
        // 服务端响应都可能包含密码、令牌或其他隐私数据，禁止写入浏览器日志。
        if (response.status === 422) {
          console.error('API请求校验失败:', safeRequestMetadata(url, requestOptions, response))
        }
      } catch {
        // 如果无法解析JSON，使用默认错误信息
        console.error('API错误响应无法解析:', safeRequestMetadata(url, requestOptions, response))
      }

      const errorMessage = publicErrorMessage(
        url,
        response.status,
        response.headers,
        requiresAuth,
        errorData
      )
      // 特殊处理401和403错误
      const error = new Error(errorMessage)
      error.status = response.status
      error.headers = safeResponseHeaders(response.headers)
      error.response = {
        status: response.status,
        data: safeErrorData(errorData, response.status, errorMessage),
        headers: error.headers
      }

      if (response.status === 401 && requiresAuth) {
        // 如果是认证失败，可能需要重新登录
        const userStore = useUserStore()

        message.error('登录已过期，请重新登录')

        // 如果用户当前认为自己已登录，则登出
        if (userStore.isLoggedIn) {
          userStore.logout()
        }

        // 使用setTimeout确保消息显示后再跳转
        setTimeout(() => {
          window.location.href = '/login'
        }, 1500)

        throw error
      } else if (response.status === 403) {
        throw error
      } else if (response.status === 500) {
        throw error
      }

      throw error
    }

    // 根据responseType处理响应
    if (responseType === 'blob') {
      return response
    } else if (responseType === 'json') {
      // 检查Content-Type以确定如何处理响应
      const contentType = response.headers.get('Content-Type')
      if (contentType && contentType.includes('application/json')) {
        return await response.json()
      }
      return await response.text()
    } else if (responseType === 'text') {
      return await response.text()
    } else {
      return response
    }
  } catch (error) {
    if (error.name !== 'AbortError') {
      console.error('API请求异常:', {
        ...safeRequestMetadata(url, options),
        status: error?.status ?? null,
        errorType: error?.name || 'Error'
      })
    }
    throw error
  }
}

/**
 * 发送GET请求
 * @param {string} url - API端点
 * @param {Object} options - 请求选项
 * @param {boolean} requiresAuth - 是否需要认证
 * @param {string} responseType - 响应类型: 'json' | 'text' | 'blob'
 * @returns {Promise} - 请求结果
 */
export function apiGet(url, options = {}, requiresAuth = true, responseType = 'json') {
  return apiRequest(url, { method: 'GET', ...options }, requiresAuth, responseType)
}

export function apiAdminGet(url, options = {}, responseType = 'json') {
  checkAdminPermission()
  return apiGet(url, options, true, responseType)
}

export function apiSuperAdminGet(url, options = {}, responseType = 'json') {
  checkSuperAdminPermission()
  return apiGet(url, options, true, responseType)
}

/**
 * 发送POST请求
 * @param {string} url - API端点
 * @param {Object} data - 请求体数据
 * @param {Object} options - 其他请求选项
 * @param {boolean} requiresAuth - 是否需要认证
 * @param {string} responseType - 响应类型: 'json' | 'text' | 'blob'
 * @returns {Promise} - 请求结果
 */
export function apiPost(url, data = {}, options = {}, requiresAuth = true, responseType = 'json') {
  return apiRequest(
    url,
    {
      method: 'POST',
      body: data instanceof FormData ? data : JSON.stringify(data),
      ...options
    },
    requiresAuth,
    responseType
  )
}

export function apiAdminPost(url, data = {}, options = {}, responseType = 'json') {
  checkAdminPermission()
  return apiPost(url, data, options, true, responseType)
}

export function apiSuperAdminPost(url, data = {}, options = {}, responseType = 'json') {
  checkSuperAdminPermission()
  return apiPost(url, data, options, true, responseType)
}

/**
 * 发送PUT请求
 * @param {string} url - API端点
 * @param {Object} data - 请求体数据
 * @param {Object} options - 其他请求选项
 * @param {boolean} requiresAuth - 是否需要认证
 * @param {string} responseType - 响应类型: 'json' | 'text' | 'blob'
 * @returns {Promise} - 请求结果
 */
export function apiPut(url, data = {}, options = {}, requiresAuth = true, responseType = 'json') {
  return apiRequest(
    url,
    {
      method: 'PUT',
      body: data instanceof FormData ? data : JSON.stringify(data),
      ...options
    },
    requiresAuth,
    responseType
  )
}

export function apiAdminPut(url, data = {}, options = {}, responseType = 'json') {
  checkAdminPermission()
  return apiPut(url, data, options, true, responseType)
}

export function apiSuperAdminPut(url, data = {}, options = {}, responseType = 'json') {
  checkSuperAdminPermission()
  return apiPut(url, data, options, true, responseType)
}

/**
 * 发送DELETE请求
 * @param {string} url - API端点
 * @param {Object} options - 请求选项
 * @param {boolean} requiresAuth - 是否需要认证
 * @param {string} responseType - 响应类型: 'json' | 'text' | 'blob'
 * @returns {Promise} - 请求结果
 */
export function apiDelete(url, options = {}, requiresAuth = true, responseType = 'json') {
  return apiRequest(url, { method: 'DELETE', ...options }, requiresAuth, responseType)
}

export function apiAdminDelete(url, options = {}) {
  checkAdminPermission()
  return apiDelete(url, options, true)
}

export function apiSuperAdminDelete(url, options = {}) {
  checkSuperAdminPermission()
  return apiDelete(url, options, true)
}
