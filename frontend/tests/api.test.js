import { afterEach, expect, test, vi } from 'vitest'
import { getChats } from '../src/services/api.js'
afterEach(() => vi.unstubAllGlobals())
test('기록 조회는 세션 쿠키를 사용하고 사용자 ID를 보내지 않음', async () => {
  const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ chats: [] }) }))
  vi.stubGlobal('fetch', fetchMock)
  expect(await getChats()).toEqual([])
  expect(fetchMock.mock.calls[0][0]).toBe('/api/me/chats')
  expect(fetchMock.mock.calls[0][1].credentials).toBe('include')
})
test.each([
  {}, { chats: null }, { chats: [{ id: 1, question: 'q', answer: 'a', created_at: 'invalid' }] },
  { chats: [{ id: 1, question: 'q', answer: 'a', created_at: '2026-10-08T12:00:00' }] },
])('잘못된 기록 응답을 화면에 사용하지 않음: %j', async body => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => body })))
  await expect(getChats()).rejects.toThrow('Invalid history response')
})
