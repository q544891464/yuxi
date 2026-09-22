// 与服务端页面目录对应；这里只负责隐藏入口，导航决策由服务端返回。
export function canVisitPage(pages, path) {
  if (pages === null) return true
  if (!Array.isArray(pages)) return false
  let root
  if (path.startsWith('/chat/knowledge/')) root = '/extensions'
  else if (path === '/chat/dashboard') root = '/dashboard'
  else
    root = [
      '/chat/ducha',
      '/agent-manage',
      '/extensions',
      '/workspace',
      '/dashboard',
      '/agent',
      '/chat'
    ].find((base) => path === base || path.startsWith(base + '/'))
  return pages.includes(root)
}
