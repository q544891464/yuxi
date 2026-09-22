/** 使用可取消的上传传输，并交回统一 API 边界处理认证和响应错误。 */
export function uploadTransport(url, options, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const abort = () => xhr.abort()
    const cleanup = () => options.signal?.removeEventListener('abort', abort)
    if (options.signal?.aborted) {
      reject(new DOMException('上传已取消', 'AbortError'))
      return
    }
    xhr.open(options.method || 'POST', url)
    for (const [name, value] of Object.entries(options.headers || {})) {
      xhr.setRequestHeader(name, value)
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100))
    }
    xhr.onload = () => {
      cleanup()
      resolve(
        new Response(xhr.status === 204 ? null : xhr.responseText, {
          status: xhr.status,
          headers: {
            'content-type': xhr.getResponseHeader('content-type') || '',
            'retry-after': xhr.getResponseHeader('retry-after') || '',
            'x-lock-remaining': xhr.getResponseHeader('x-lock-remaining') || '',
            'www-authenticate': xhr.getResponseHeader('www-authenticate') || ''
          }
        })
      )
    }
    xhr.onerror = () => {
      cleanup()
      reject(new TypeError('上传连接失败'))
    }
    xhr.onabort = () => {
      cleanup()
      reject(new DOMException('上传已取消', 'AbortError'))
    }
    options.signal?.addEventListener('abort', abort, { once: true })
    try {
      xhr.send(options.body)
    } catch (error) {
      cleanup()
      reject(error)
    }
  })
}
