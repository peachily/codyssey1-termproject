import { expect, test } from 'vitest'
import { groupChats, historyDate, historyTime } from '../src/components/history/historyDates.js'

test.each([
  ['2026-10-07T14:59:59Z', '2026-10-07'],
  ['2026-10-07T15:00:00Z', '2026-10-08'],
  ['2026-10-31T15:00:00Z', '2026-11-01'],
  ['2026-12-31T15:00:00Z', '2027-01-01'],
  ['2028-02-28T15:00:00Z', '2028-02-29'],
])('한국 날짜 경계: %s', (instant, expected) => expect(historyDate(instant)).toBe(expected))

test('질문·답변을 시간순, 동시각이면 ID순으로 묶고 원본을 변경하지 않음', () => {
  const chats = [
    { id: 3, created_at: '2026-12-31T15:00:00Z' },
    { id: 2, created_at: '2026-12-31T15:00:00Z' },
    { id: 1, created_at: '2026-12-31T14:59:00Z' },
  ]
  const groups = groupChats(chats)
  expect(groups.get('2027-01-01').map(chat => chat.id)).toEqual([2, 3])
  expect(groups.get('2026-12-31').map(chat => chat.id)).toEqual([1])
  expect(chats.map(chat => chat.id)).toEqual([3, 2, 1])
  expect(historyTime(chats[0].created_at)).toBe('00:00')
})
