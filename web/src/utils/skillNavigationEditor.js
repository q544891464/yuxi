/** 为新入口生成稳定且低碰撞的标识。 */
export function createNavigationEntryId() {
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16))
  return `entry-${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`
}

/** 将导航树展开为保留同级顺序的编辑行。 */
export function navigationRows(tree, parentId = '') {
  return tree.flatMap(({ children = [], ...node }) => [
    { ...node, kind: node.skillSlug ? 'entry' : 'group', parentId },
    ...navigationRows(children, node.id)
  ])
}

/** 返回节点的全部后代标识。 */
export function descendantIds(rows, id) {
  return rows
    .filter((row) => row.parentId === id)
    .flatMap((row) => [row.id, ...descendantIds(rows, row.id)])
}

/** 按编辑行的父子关系生成服务端树并校验深度和循环。 */
export function navigationTree(rows) {
  const seen = new Set()
  const build = (parentId, depth) =>
    rows
      .filter((row) => row.parentId === parentId)
      .map((row) => {
        if (depth > 3 || seen.has(row.id)) throw new Error('侧栏技能最多三级，且不能循环嵌套')
        seen.add(row.id)
        const node = { ...row }
        delete node.parentId
        delete node.kind
        return { ...node, children: build(row.id, depth + 1) }
      })
  const tree = build('', 1)
  if (seen.size !== rows.length) throw new Error('存在无效父级，请调整层级')
  return tree
}

/** 仅调整同级节点顺序。 */
export function moveNavigationRow(rows, id, direction) {
  const index = rows.findIndex((row) => row.id === id)
  if (index < 0) return
  const siblings = rows.filter((row) => row.parentId === rows[index].parentId)
  const target = siblings[siblings.findIndex((row) => row.id === id) + direction]
  if (!target) return
  const other = rows.findIndex((row) => row.id === target.id)
  ;[rows[index], rows[other]] = [rows[other], rows[index]]
}
