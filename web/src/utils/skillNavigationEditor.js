/** 生成入口标识；getRandomValues 在普通 HTTP 页面也可用。 */
export function createNavigationEntryId() {
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16))
  return `entry-${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`
}

/** 将导航树转换成保留顺序的编辑行。 */
export function navigationRows(nodes, parentId = '') {
  return nodes.flatMap(({ children = [], ...node }) => [
    { ...node, parentId },
    ...navigationRows(children, node.id)
  ])
}

/** 查找整个子树，用于删除确认和排除循环父级。 */
export function descendantIds(rows, id) {
  return rows
    .filter((row) => row.parentId === id)
    .flatMap((row) => [row.id, ...descendantIds(rows, row.id)])
}

/** 编辑数据生成服务端认可的有序树，不丢弃孤立或循环节点。 */
export function navigationTree(rows) {
  const seen = new Set()
  const build = (parentId, depth) =>
    rows
      .filter((row) => row.parentId === parentId)
      .map((row) => {
        if (depth > 3 || seen.has(row.id)) throw new Error('入口最多三级，且不能循环嵌套')
        seen.add(row.id)
        const node = { ...row }
        delete node.parentId
        return { ...node, children: build(row.id, depth + 1) }
      })
  const nodes = build('', 1)
  if (seen.size !== rows.length) throw new Error('父级无效或存在循环，请调整层级')
  return nodes
}

/** 只交换同级顺序，子入口随父级展示。 */
export function moveNavigationRow(rows, id, direction) {
  const index = rows.findIndex((row) => row.id === id)
  if (index < 0) return
  const siblings = rows.filter((row) => row.parentId === rows[index].parentId)
  const target = siblings[siblings.findIndex((row) => row.id === id) + direction]
  if (!target) return
  const other = rows.findIndex((row) => row.id === target.id)
  ;[rows[index], rows[other]] = [rows[other], rows[index]]
}
