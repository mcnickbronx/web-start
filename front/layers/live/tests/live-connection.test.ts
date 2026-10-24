import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createLiveConnection, liveUrl, type LiveConnectionOptions, type LiveEvent, type LiveStatus } from '../app/utils/live-connection'

/** Поддельный WebSocket: что слой послал и закрыл ли; open, receive и drop — как будто это сделал сервер */
class FakeSocket {
  sentList: unknown[] = []
  isClosed = false
  onopen: (() => void) | null = null
  onmessage: ((message: { data: unknown }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  constructor(public url: string) {}
  send(data: string) {
    this.sentList.push(JSON.parse(data))
  }

  close() {
    this.isClosed = true
  }

  open() {
    this.onopen?.()
  }

  receive(data: string) {
    this.onmessage?.({ data })
  }

  drop(code = 1006) {
    this.onclose?.({ code })
  }
}

function setup(options: Partial<LiveConnectionOptions> = {}, tokenFirst: string | null = 'access-1') {
  let token = tokenFirst
  const socketList: FakeSocket[] = []
  const eventList: LiveEvent[] = []
  const statusList: LiveStatus[] = []
  const connection = createLiveConnection({
    url: liveUrl('https://back.example.com'),
    getToken: () => token,
    onEvent: event => eventList.push(event),
    onStatus: status => statusList.push(status),
    createSocket: (url) => {
      const socket = new FakeSocket(url)
      socketList.push(socket)
      return socket as unknown as WebSocket
    },
    ...options,
  })
  /** Соединение открылось и сервер принял токен */
  const ready = (socket: FakeSocket) => {
    socket.open()
    socket.receive('{"type": "ready"}')
  }
  return { connection, socketList, eventList, statusList, ready, setToken: (value: string | null) => (token = value) }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('адрес и вход', () => {
  it('адрес — от apiBase: http → ws, https → wss, без токена', () => {
    expect(liveUrl('http://localhost:8000')).toBe('ws://localhost:8000/api/live/ws')
    expect(liveUrl('https://back.example.com/')).toBe('wss://back.example.com/api/live/ws')
  })

  it('первое сообщение — auth с токеном, после ready — на связи', () => {
    const { connection, socketList, statusList } = setup()
    connection.connect()
    expect(socketList).toHaveLength(1)
    const [socket] = socketList
    expect(socket.url).toBe('wss://back.example.com/api/live/ws')
    expect(socket.url).not.toContain('access-1')
    expect(socket.sentList).toEqual([])
    socket.open()
    expect(socket.sentList).toEqual([{ type: 'auth', token: 'access-1' }])
    expect(statusList.at(-1)).toBe('connecting')
    socket.receive('{"type": "ready"}')
    expect(statusList.at(-1)).toBe('ready')
  })

  it('без токена — ни одного соединения; токен появился — соединение', () => {
    const { connection, socketList, statusList, setToken } = setup({}, null)
    connection.connect()
    expect(socketList).toHaveLength(0)
    expect(statusList).toEqual(['idle'])
    setToken('access-1')
    connection.connect()
    connection.connect()
    expect(socketList).toHaveLength(1)
  })

  it('токен сменился (вошёл другой) — старое соединение закрыто, новое — с новым токеном', () => {
    const { connection, socketList, ready, setToken } = setup()
    connection.connect()
    ready(socketList[0])
    setToken('access-other')
    connection.connect()
    expect(socketList[0].isClosed).toBe(true)
    expect(socketList).toHaveLength(2)
    socketList[1].open()
    expect(socketList[1].sentList).toEqual([{ type: 'auth', token: 'access-other' }])
  })

  it('токен пропал (выход) — соединение закрыто', () => {
    const { connection, socketList, statusList, ready, setToken } = setup()
    connection.connect()
    ready(socketList[0])
    setToken(null)
    connection.connect()
    expect(socketList[0].isClosed).toBe(true)
    expect(statusList.at(-1)).toBe('idle')
  })
})

describe('события', () => {
  it('событие — в onEvent; ready, pong, не JSON и не объект с type — нет', () => {
    const { connection, socketList, eventList, ready } = setup()
    connection.connect()
    ready(socketList[0])
    for (const data of ['{"type": "pong"}', 'не JSON', '[1]', '"notice"', 'null', '{"title": "без type"}', '{"type": 1}']) {
      socketList[0].receive(data)
    }
    socketList[0].receive('{"type": "notice", "title": "Заказ оплачен"}')
    expect(eventList).toEqual([{ type: 'notice', title: 'Заказ оплачен' }])
  })
})

describe('обрыв', () => {
  it('переподключение через 1 с, потом 2, 5, 10, 30, 30 с', async () => {
    const { connection, socketList, statusList, ready } = setup()
    connection.connect()
    ready(socketList[0])
    for (const [index, delay] of [1000, 2000, 5000, 10_000, 30_000, 30_000].entries()) {
      socketList[index].drop()
      expect(statusList.at(-1)).toBe('connecting')
      await vi.advanceTimersByTimeAsync(delay - 1)
      expect(socketList).toHaveLength(index + 1)
      await vi.advanceTimersByTimeAsync(1)
      expect(socketList).toHaveLength(index + 2)
    }
  })

  it('после ready паузы снова с 1 с', async () => {
    const { connection, socketList, ready } = setup()
    connection.connect()
    socketList[0].drop()
    await vi.advanceTimersByTimeAsync(1000)
    socketList[1].drop()
    await vi.advanceTimersByTimeAsync(2000)
    ready(socketList[2])
    socketList[2].drop()
    await vi.advanceTimersByTimeAsync(1000)
    expect(socketList).toHaveLength(4)
  })
})

describe('4401 — сервер не принял токен', () => {
  it('одно обновление токена и сразу новое соединение с новым; второй 4401 подряд — нужен вход', async () => {
    // Как слой user: новый токен — и в ответ, и в useAccessToken()
    const refreshToken = vi.fn(async () => live.setToken('access-2'))
    const live = setup({ refreshToken })
    const { connection, socketList, statusList } = live
    connection.connect()
    socketList[0].open()
    socketList[0].drop(4401)
    await vi.advanceTimersByTimeAsync(0)
    expect(refreshToken).toHaveBeenCalledTimes(1)
    expect(socketList).toHaveLength(2)
    socketList[1].open()
    expect(socketList[1].sentList).toEqual([{ type: 'auth', token: 'access-2' }])

    socketList[1].drop(4401)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(refreshToken).toHaveBeenCalledTimes(1)
    expect(socketList).toHaveLength(2)
    expect(statusList.at(-1)).toBe('unauthorized')

    // С тем же токеном не стучимся; вошёл заново — новый токен, новое соединение
    connection.connect()
    expect(socketList).toHaveLength(2)
    live.setToken('access-3')
    connection.connect()
    expect(socketList).toHaveLength(3)
  })

  it('после ready 4401 снова обновляет токен', async () => {
    const refreshToken = vi.fn(async () => 'access-2')
    const { connection, socketList, ready } = setup({ refreshToken })
    connection.connect()
    ready(socketList[0])
    socketList[0].drop(4401)
    await vi.advanceTimersByTimeAsync(0)
    ready(socketList[1])
    socketList[1].drop(4401)
    await vi.advanceTimersByTimeAsync(0)
    expect(refreshToken).toHaveBeenCalledTimes(2)
    expect(socketList).toHaveLength(3)
  })

  it('обновить нечем (нет слоя user) или не вышло — нужен вход, без переподключения', async () => {
    for (const options of [{}, { refreshToken: async () => null }, { refreshToken: () => Promise.reject(new Error('сеть')) }]) {
      const { connection, socketList, statusList } = setup(options)
      connection.connect()
      socketList[0].drop(4401)
      await vi.advanceTimersByTimeAsync(60_000)
      expect(socketList).toHaveLength(1)
      expect(statusList.at(-1)).toBe('unauthorized')
    }
  })
})

describe('close()', () => {
  it('закрывает соединение, и обрыв после этого не переподключает', async () => {
    const { connection, socketList, statusList, ready } = setup()
    connection.connect()
    ready(socketList[0])
    connection.close()
    expect(socketList[0].isClosed).toBe(true)
    expect(statusList.at(-1)).toBe('idle')
    socketList[0].drop(1000)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(socketList).toHaveLength(1)
  })

  it('во время паузы и во время обновления токена — нового соединения нет', async () => {
    const { connection, socketList } = setup({ refreshToken: async () => 'access-2' })
    connection.connect()
    socketList[0].drop()
    connection.close()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(socketList).toHaveLength(1)

    connection.connect()
    socketList[1].drop(4401)
    connection.close()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(socketList).toHaveLength(2)
  })
})
