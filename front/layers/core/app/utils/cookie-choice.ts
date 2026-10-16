/** Ответ посетителя на уведомление о cookie — в localStorage браузера */
export const COOKIE_CHOICE_KEY = 'cookie-choice'

export type CookieChoice = 'accepted' | 'declined'

/** Что ответил посетитель; не отвечал или браузер не даёт localStorage — null */
export function readCookieChoice(): CookieChoice | null {
  try {
    const value = localStorage.getItem(COOKIE_CHOICE_KEY)
    return value === 'accepted' || value === 'declined' ? value : null
  }
  catch {
    return null
  }
}

export function saveCookieChoice(choice: CookieChoice) {
  try {
    localStorage.setItem(COOKIE_CHOICE_KEY, choice)
  }
  catch { /* нет localStorage — спросим снова в следующий раз */ }
}
