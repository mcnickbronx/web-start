/** Состояние соединения: idle — не подключены (нет токена или закрыли сами), connecting — открываем или ждём паузу
 * после обрыва, ready — сервер принял токен, unauthorized — сервер не принял токен и после обновления, нужен вход */
export type LiveStatus = 'idle' | 'connecting' | 'ready' | 'unauthorized'

/** Событие от сервера: `type` и поля, которые задаёт модуль, который его шлёт */
export type LiveEvent = { type: string } & Record<string, unknown>

export interface LiveConnectionOptions {
  url: string
  getToken: () => string | null
  /** Новый access-токен (слой user); нет — на 4401 второго шанса нет */
  refreshToken?: () => Promise<string | null>
  onEvent: (event: LiveEvent) => void
  onStatus: (status: LiveStatus) => void
  createSocket?: (url: string) => WebSocket
}

/** Код закрытия «не вошёл» модуля live бэкенда */
export const CLOSE_UNAUTHORIZED = 4401
/** Паузы перед переподключением после обрыва, мс: сервер, который лежит, не долбим чаще раза в 30 с */
export const RECONNECT_DELAY_LIST = [1000, 2000, 5000, 10_000, 30_000]

/** Адрес WebSocket по адресу API: http → ws, https → wss. Токен в адрес не кладём — адрес пишут журналы */
export function liveUrl(apiBase: string) {
  return `${apiBase.replace(/\/+$/, '').replace(/^http/, 'ws')}/api/live/ws`
}

/**
 * Соединение с модулем live: токен первым сообщением, события — в onEvent, обрыв — переподключение
 * с растущей паузой, 4401 — одно обновление токена и сразу новое соединение.
 * connect() приводит соединение к текущему токену, close() — закрывает и больше не переподключается.
 */
export function createLiveConnection(options: LiveConnectionOptions) {
  const createSocket = options.createSocket ?? (url => new WebSocket(url))
  let socket: WebSocket | null = null
  let socketToken: string | null = null // токен открытого соединения или того, что ждёт паузу и обновление
  let timer: ReturnType<typeof setTimeout> | undefined
  let generation = 0 // меняется при каждом открытии и закрытии: ответ обновления токена для старого — выбросить
  let attempt = 0
  let isRefreshTried = false

  function stop() {
    generation++
    clearTimeout(timer)
    const socketOld = socket
    socket = null // обработчики старого соединения смотрят сюда и молчат
    socketOld?.close()
  }

  function open(token: string) {
    stop()
    socketToken = token
    options.onStatus('connecting')
    const socketNew = createSocket(options.url)
    socket = socketNew
    socketNew.onopen = () => {
      if (socket === socketNew) {
        socketNew.send(JSON.stringify({ type: 'auth', token }))
      }
    }
    socketNew.onmessage = (message) => {
      if (socket === socketNew) {
        receive(message.data)
      }
    }
    socketNew.onclose = (event) => {
      if (socket === socketNew) {
        socket = null
        lost(event.code)
      }
    }
  }

  function receive(data: unknown) {
    let event: unknown
    try {
      event = JSON.parse(String(data))
    } catch {
      return
    }
    if (!event || typeof event !== 'object' || typeof (event as LiveEvent).type !== 'string') {
      return
    }
    const { type } = event as LiveEvent
    if (type === 'ready') {
      attempt = 0
      isRefreshTried = false
      options.onStatus('ready')
    } else if (type !== 'pong') {
      options.onEvent(event as LiveEvent)
    }
  }

  function lost(code: number) {
    if (code === CLOSE_UNAUTHORIZED) {
      refresh()
      return
    }
    options.onStatus('connecting')
    const delay = RECONNECT_DELAY_LIST[Math.min(attempt, RECONNECT_DELAY_LIST.length - 1)]
    attempt++
    timer = setTimeout(() => {
      const token = options.getToken()
      if (token) {
        open(token)
      } else {
        close()
      }
    }, delay)
  }

  /** 4401: токен просрочен или сессию закрыли — одно обновление; второй 4401 подряд (без ready между) — нужен вход */
  function refresh() {
    if (isRefreshTried || !options.refreshToken) {
      options.onStatus('unauthorized')
      return
    }
    isRefreshTried = true
    options.onStatus('connecting')
    const generationRefresh = generation
    options.refreshToken().catch(() => null).then((token) => {
      if (generationRefresh !== generation) {
        return // пока ждали, закрыли или переподключились с новым токеном
      }
      if (token) {
        open(token)
      } else {
        options.onStatus('unauthorized')
      }
    })
  }

  /** Подключиться с текущим токеном: уже с ним — ничего; токен другой — новое соединение; токена нет — закрыть */
  function connect() {
    const token = options.getToken()
    if (!token) {
      close()
    } else if (token !== socketToken) {
      open(token)
    }
  }

  function close() {
    stop()
    socketToken = null
    attempt = 0
    isRefreshTried = false
    options.onStatus('idle')
  }

  return { connect, close }
}
