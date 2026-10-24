import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, describe, expect, it } from 'vitest'
import { readDependencies, versionDiff } from '../version-guard'

const engine = { 'nuxt': '4.6.2', 'vue': '3.5.44', 'vue-router': '5.4.0', '@nuxt/ui': '4.11.2' }

describe('versionDiff', () => {
  it('версии как у движка — пусто', () => {
    expect(versionDiff(engine, { 'nuxt': '4.6.2', 'vue': '3.5.44', 'vue-router': '5.4.0' })).toEqual([])
  })

  it('другая версия — что на что поменять', () => {
    expect(versionDiff(engine, { 'nuxt': '4.5.2', 'vue': '3.5.44', 'vue-router': '5.4.0' })).toEqual(['nuxt 4.5.2 → 4.6.2'])
  })

  it('диапазон вместо точной версии — тоже расхождение', () => {
    expect(versionDiff(engine, { 'nuxt': '^4.6.2', 'vue': '^3.5.44', 'vue-router': '5.4.0' }))
      .toEqual(['nuxt ^4.6.2 → 4.6.2', 'vue ^3.5.44 → 3.5.44'])
  })

  it('не объявленное у сайта и пакеты не из правила — не проверяются', () => {
    expect(versionDiff(engine, { 'nuxt': '4.6.2', 'vue': '3.5.44', '@nuxt/ui': '4.0.0' })).toEqual([])
  })

  it('нет package.json сайта или движка — пусто', () => {
    expect(versionDiff(engine, undefined)).toEqual([])
    expect(versionDiff(undefined, { nuxt: '4.5.2' })).toEqual([])
  })
})

describe('readDependencies', () => {
  const dir = mkdtempSync(join(tmpdir(), 'version-guard-'))
  afterAll(() => rmSync(dir, { recursive: true, force: true }))

  it('dependencies из package.json', () => {
    const file = join(dir, 'package.json')
    writeFileSync(file, JSON.stringify({ name: 'site', dependencies: { nuxt: '4.6.2' } }))
    expect(readDependencies(file)).toEqual({ nuxt: '4.6.2' })
  })

  it('нет файла или битый JSON — undefined, без исключения', () => {
    expect(readDependencies(join(dir, 'missing.json'))).toBeUndefined()
    const broken = join(dir, 'broken.json')
    writeFileSync(broken, '{ "dependencies": ')
    expect(readDependencies(broken)).toBeUndefined()
  })
})
