import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { build, createServer } from 'vite'

const cmapPath = '/assets/pdfjs-cmaps/UniGB-UCS2-H.bcmap'
const runtimeAssets = [
  {
    url: '/assets/pdfjs-wasm/jbig2.wasm',
    source: '../../node_modules/pdfjs-dist/wasm/jbig2.wasm'
  },
  {
    url: '/assets/pdfjs-wasm/openjpeg.wasm',
    source: '../../node_modules/pdfjs-dist/wasm/openjpeg.wasm'
  },
  {
    url: '/assets/pdfjs-wasm/qcms_bg.wasm',
    source: '../../node_modules/pdfjs-dist/wasm/qcms_bg.wasm'
  },
  {
    url: '/assets/pdfjs-wasm/jbig2_nowasm_fallback.js',
    source: '../../node_modules/pdfjs-dist/wasm/jbig2_nowasm_fallback.js'
  },
  {
    url: '/assets/pdfjs-wasm/openjpeg_nowasm_fallback.js',
    source: '../../node_modules/pdfjs-dist/wasm/openjpeg_nowasm_fallback.js'
  },
  {
    url: '/assets/pdfjs-standard-fonts/FoxitSerif.pfb',
    source: '../../node_modules/pdfjs-dist/standard_fonts/FoxitSerif.pfb'
  }
]

test('PDF.js CMap、WASM 与标准字体在开发和构建中均由应用本地提供', async () => {
  const expected = await readFile(
    new URL('../../node_modules/pdfjs-dist/cmaps/UniGB-UCS2-H.bcmap', import.meta.url)
  )
  const component = await readFile(
    new URL('../../src/components/common/PdfPreview.vue', import.meta.url),
    'utf8'
  )
  assert.match(component, /cMapUrl: '\/assets\/pdfjs-cmaps\/'/)
  assert.match(component, /standardFontDataUrl: '\/assets\/pdfjs-standard-fonts\/'/)
  assert.match(component, /wasmUrl: '\/assets\/pdfjs-wasm\/'/)
  assert.doesNotMatch(component, /cdn\.jsdelivr/)
  const server = await createServer({ server: { host: '127.0.0.1', port: 0 } })
  try {
    await server.listen()
    const response = await fetch(`http://127.0.0.1:${server.httpServer.address().port}${cmapPath}`)
    assert.equal(response.status, 200)
    assert.match(response.headers.get('content-type'), /application\/octet-stream/)
    assert.deepEqual(Buffer.from(await response.arrayBuffer()), expected)
    for (const asset of runtimeAssets) {
      const assetResponse = await fetch(
        `http://127.0.0.1:${server.httpServer.address().port}${asset.url}`
      )
      const expectedAsset = await readFile(new URL(asset.source, import.meta.url))
      assert.equal(assetResponse.status, 200, asset.url)
      const expectedContentType = asset.url.endsWith('.wasm')
        ? 'application/wasm'
        : asset.url.endsWith('.js')
          ? 'text/javascript'
          : 'application/octet-stream'
      assert.match(assetResponse.headers.get('content-type'), new RegExp(expectedContentType))
      assert.deepEqual(Buffer.from(await assetResponse.arrayBuffer()), expectedAsset, asset.url)
    }
  } finally {
    await server.close()
  }
  const result = await build({
    logLevel: 'silent',
    build: {
      write: false,
      minify: false,
      rollupOptions: {
        input: fileURLToPath(new URL('../../src/utils/pdfPreviewErrors.js', import.meta.url))
      }
    }
  })
  const asset = result.output.find((entry) => entry.fileName === cmapPath.slice(1))
  assert.ok(asset, '构建产物必须包含本地 CMap')
  assert.deepEqual(Buffer.from(asset.source), expected)
  for (const runtimeAsset of runtimeAssets) {
    const asset = result.output.find((entry) => entry.fileName === runtimeAsset.url.slice(1))
    assert.ok(asset, `构建产物必须包含 ${runtimeAsset.url}`)
    assert.deepEqual(
      Buffer.from(asset.source),
      await readFile(new URL(runtimeAsset.source, import.meta.url))
    )
  }
})
