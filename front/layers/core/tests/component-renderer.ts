import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { compileScript, parse } from 'vue/compiler-sfc'
import ts from 'typescript'

// Компилируем настоящий SFC и выполняем Vue lifecycle без DOM, браузера и внешних запросов.
export function component(path: URL) {
  const { descriptor } = parse(readFileSync(path, 'utf8'), { filename: path.pathname })
  const script = compileScript(descriptor, { id: 'test', inlineTemplate: true })
  const code = ts.transpileModule(script.content, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  const exports: { default?: Vue.Component } = {}
  new Function('require', 'exports', code)((name: string) => {
    if (name !== 'vue') throw new Error(`Неожиданный импорт: ${name}`)
    return Vue
  }, exports)
  return exports.default!
}

type Node = { type: string, props: Record<string, any>, children: Node[], parent?: Node, text?: string }
const node = (type: string): Node => ({ type, props: {}, children: [] })
const renderer = Vue.createRenderer<Node, Node>({
  createElement: node, createText: text => ({ ...node('#text'), text }), createComment: node,
  setText: (node, text) => { node.text = text },
  setElementText: (node, text) => { node.text = text; node.children = [] },
  patchProp: (node, key, _old, value) => { node.props[key] = value },
  parentNode: node => node.parent ?? null,
  nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] ?? null,
  insert: (node, parent, anchor) => {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    node.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    parent.children.splice(index < 0 ? parent.children.length : index, 0, node)
  },
  remove: node => { node.parent?.children.splice(node.parent.children.indexOf(node), 1) },
})

export function mount(path: URL, plugin?: Vue.Plugin) {
  const root = node('root')
  const app = renderer.createApp(component(path))
  for (const name of ['ULink', 'UButton', 'UPageCard', 'UFormField', 'UCheckbox', 'UInput', 'UAuthForm', 'UAlert', 'FormTrap', 'FormSmartCaptcha', 'UFileUpload']) {
    app.component(name, {
      inheritAttrs: false,
      setup: (_props, { attrs, slots }) => () => Vue.h(name, attrs, [attrs.label, ...Object.values(slots).flatMap(slot => slot?.() ?? [])]),
    })
  }
  if (plugin) app.use(plugin)
  app.mount(root)
  const find = (type: string): Node[] => {
    const visit = (n: Node): Node[] => [...(n.type === type ? [n] : []), ...n.children.flatMap(visit)]
    return visit(root)
  }
  return { find, unmount: () => app.unmount() }
}
