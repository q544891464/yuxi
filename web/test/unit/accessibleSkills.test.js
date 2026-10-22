import assert from 'node:assert/strict'
import test from 'node:test'

import { createServer } from 'vite'

test('员工技能取启用配置与可访问技能的交集', async () => {
  const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
  try {
    const { filterEnabledAgentSkills } = await server.ssrLoadModule('/src/utils/accessibleSkills.js')
    const accessible = [
      { slug: 'shared-a' },
      { slug: 'shared-b' },
      { slug: 'personal-c', source_scope: 'personal' }
    ]

    assert.deepEqual(filterEnabledAgentSkills(accessible, ['shared-b', 'personal-c']), [
      accessible[1],
      accessible[2]
    ])
    assert.deepEqual(filterEnabledAgentSkills(accessible, ['unknown']), [])
    assert.deepEqual(filterEnabledAgentSkills(accessible, undefined), [])
    assert.deepEqual(filterEnabledAgentSkills(accessible, 'all'), accessible)
  } finally {
    await server.close()
  }
})
