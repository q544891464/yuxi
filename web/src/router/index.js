import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { getDuchaPage } from '@/apis/system_api'
import { sanitizeRedirect } from '@/utils/oidcAutoStart'

const AppLayout = () => import('@/layouts/AppLayout.vue')

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'Home',
      redirect: '/agent'
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/auth/oidc/callback', // oidc登录回调页面
      name: 'OIDCCallback',
      component: () => import('@/views/OIDCCallbackView.vue'),
      meta: { public: true }
    },
    {
      path: '/auth/cli/authorize',
      name: 'CLIAuthAuthorize',
      component: () => import('@/views/CLIAuthAuthorizeView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/chat',
      component: AppLayout,
      meta: { requiresAuth: true, consumerChat: true },
      children: [
        { path: '', name: 'ChatComp', component: () => import('../views/AgentView.vue') },
        {
          path: 'ducha',
          name: 'DuchaChatComp',
          component: () => import('../views/AgentView.vue'),
          meta: { ducha: true }
        },
        {
          path: 'ducha/:thread_id',
          name: 'DuchaChatCompWithThreadId',
          component: () => import('../views/AgentView.vue'),
          meta: { ducha: true }
        },
        {
          path: 'knowledge/:kbId',
          name: 'ConsumerKnowledgeBaseDetail',
          component: () => import('../views/DataBaseInfoView.vue'),
          meta: { keepAlive: true, requiresAuth: true }
        },
        {
          path: 'dashboard',
          name: 'ConsumerDashboard',
          component: () => import('../views/DashboardView.vue'),
          meta: { keepAlive: true, requiresAuth: true, requiresAdmin: true }
        },
        {
          path: ':thread_id',
          name: 'ChatCompWithThreadId',
          component: () => import('../views/AgentView.vue')
        }
      ]
    },
    {
      path: '/agent',
      name: 'AgentMain',
      meta: { requiresAuth: true, requiresAdmin: true },
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'AgentComp',
          component: () => import('../views/AgentView.vue'),
          meta: { keepAlive: true, requiresAuth: true }
        },
        {
          path: ':thread_id',
          name: 'AgentCompWithThreadId',
          component: () => import('../views/AgentView.vue'),
          meta: { keepAlive: true, requiresAuth: true }
        }
      ]
    },
    {
      path: '/workspace',
      name: 'workspace',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'WorkspaceComp',
          component: () => import('../views/WorkspaceView.vue'),
          meta: { keepAlive: true, requiresAuth: true }
        }
      ]
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'DashboardComp',
          component: () => import('../views/DashboardView.vue'),
          meta: { keepAlive: false, requiresAuth: true, requiresAdmin: true }
        }
      ]
    },
    {
      path: '/agent-manage',
      name: 'agent-manage',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'AgentManageComp',
          component: () => import('../views/AgentManageView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        }
      ]
    },
    {
      path: '/extensions',
      name: 'extensions',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'ExtensionsComp',
          component: () => import('../views/ExtensionsView.vue'),
          meta: {
            keepAlive: false,
            requiresAuth: true
          },
          children: [
            {
              path: 'knowledgebase/:kbId',
              name: 'ExtensionKnowledgeBaseDetail',
              component: () => import('../views/DataBaseInfoView.vue'),
              meta: { keepAlive: false, requiresAuth: true }
            },
            {
              path: 'knowledgebase/:kbId/evaluation/:datasetId',
              name: 'ExtensionEvaluationBenchmarkDetail',
              component: () => import('../views/EvaluationBenchmarkDetailView.vue'),
              meta: {
                keepAlive: false,
                requiresAuth: true,
                requiresAdmin: true
              }
            },
            {
              path: 'mcp/:slug',
              name: 'ExtensionMcpDetail',
              component: () => import('../components/extensions/McpDetailView.vue'),
              meta: {
                keepAlive: false,
                requiresAuth: true,
                requiresAdmin: true
              }
            },
            {
              path: 'skill/:slug',
              name: 'ExtensionSkillDetail',
              component: () => import('../components/extensions/SkillDetailView.vue'),
              meta: {
                keepAlive: false,
                requiresAuth: true
              }
            }
          ]
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('../views/EmptyView.vue'),
      meta: { requiresAuth: false }
    }
  ]
})

// 全局前置守卫
router.beforeEach(async (to) => {
  // 检查路由是否需要认证
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth === true)
  const requiresAdmin = to.matched.some((record) => record.meta.requiresAdmin)
  const requiresSuperAdmin = to.matched.some((record) => record.meta.requiresSuperAdmin)

  const userStore = useUserStore()

  // 如果有 token 但用户信息未加载，先获取用户信息
  if (userStore.token && !userStore.userId) {
    try {
      await userStore.getCurrentUser()
    } catch (error) {
      // 如果获取用户信息失败（如 token 过期），清除 token
      console.error('获取用户信息失败:', error)
      userStore.logout()
    }
  }

  const isLoggedIn = userStore.isLoggedIn
  const isAdmin = userStore.isAdmin
  const isSuperAdmin = userStore.isSuperAdmin

  // 如果路由需要认证但用户未登录
  if (requiresAuth && !isLoggedIn) {
    // 保存尝试访问的路径，登录后跳转
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (to.meta.ducha) {
    try {
      await getDuchaPage()
    } catch {
      return '/chat'
    }
  }

  // 页面入口按已加载的身份分流，资源授权仍由后端执行。
  if (requiresAdmin && !isAdmin) return '/chat'
  if (requiresSuperAdmin && !isSuperAdmin) return isAdmin ? '/agent' : '/chat'

  // 如果用户已登录但访问登录页，按 redirect 参数跳转
  const shareLoginHash =
    typeof to.hash === 'string' && new URLSearchParams(to.hash.slice(1)).has('key')
  if (to.path === '/login' && isLoggedIn && !shareLoginHash) {
    return sanitizeRedirect(to.query.redirect)
  }

  // 其他情况正常导航
  return true
})

router.afterEach((to) => {
  document.title = to.meta.ducha ? '智能辅助督查数字人' : '智能辅助稽查数字人'
})

export default router
