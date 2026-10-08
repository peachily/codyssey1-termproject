export const HISTORY_TIME_ZONE = 'Asia/Seoul'
const dateFormat = new Intl.DateTimeFormat('en-CA', {
  timeZone: HISTORY_TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit',
})
const timeFormat = new Intl.DateTimeFormat('ko-KR', {
  timeZone: HISTORY_TIME_ZONE, hour: '2-digit', minute: '2-digit', hour12: false,
})

export function historyDate(value) {
  const parts = Object.fromEntries(dateFormat.formatToParts(new Date(value)).map(part => [part.type, part.value]))
  return `${parts.year}-${parts.month}-${parts.day}`
}

export const historyTime = value => timeFormat.format(new Date(value))

export function groupChats(chats) {
  const groups = new Map()
  const ordered = [...chats].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) || a.id - b.id)
  for (const chat of ordered) {
    const day = historyDate(chat.created_at)
    if (!groups.has(day)) groups.set(day, [])
    groups.get(day).push(chat)
  }
  return groups
}
