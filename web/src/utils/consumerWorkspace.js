/** 将资源页返回地址限制在消费端聊天首页或单个会话。 */
export const resolveConsumerChatReturnTarget = (returnTo) => {
  if (typeof returnTo !== 'string') return '/chat'
  return /^\/chat(?:\/[^/?#]+)?(?:[?#].*)?$/.test(returnTo) ? returnTo : '/chat'
}
