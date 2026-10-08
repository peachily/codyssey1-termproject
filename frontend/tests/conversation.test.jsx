// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import InteriorScene from '../src/scenes/InteriorScene.jsx'
import App from '../src/App.jsx'

const current = { id: 1, question: '오늘의 질문', answer: '오늘의 답변', created_at: '2026-10-07T15:00:00Z' }
const stored = [
  { id: 2, question: '두 번째 기록', answer: '두 번째 답변', created_at: '2026-10-08T01:00:00Z' },
  { id: 1, question: '첫 번째 기록', answer: '첫 번째 답변', created_at: '2026-10-07T15:00:00Z' },
]
let auth, fetchMock
const response = (data, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => data })
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-08T03:00:00Z'))
  auth = { user: { id: 1, username: 'test_user' }, pending: false, error: '', logout: vi.fn(), expire: vi.fn() }
  fetchMock = vi.fn(path => {
    if (path === '/api/auth/me') return response(auth.user)
    if (path === '/api/chat') return response(current)
    if (path === '/api/me/chats') return response({ chats: stored })
    if (path === '/api/prescription') return response({ keyword: 'STRESS', color: 'GREEN', message: '잠시 쉬어가요.' })
    throw new Error(`Unexpected request: ${path}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  // jsdom does not implement the browser's native dialog top layer/focus trap.
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); this.querySelector('button')?.focus() }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

async function send(user, text = '오늘의 질문') {
  await user.type(screen.getByRole('textbox'), text)
  await user.click(screen.getByRole('button', { name: '이야기 건네기' }))
  await screen.findByText('오늘의 답변')
}
async function openHistory(user) {
  await user.click(screen.getByRole('button', { name: '대화 기록', exact: true }))
  await screen.findByRole('grid')
  return screen.getByRole('dialog')
}

test('처방에서 로그인·현재 대화·작성 중 입력 유지하며 복귀하고 재질문·재처방 가능', async () => {
  const user = userEvent.setup()
  render(<InteriorScene auth={auth} />)
  await send(user)
  await user.type(screen.getByRole('textbox'), '이어서 할 이야기')
  await user.click(screen.getByRole('button', { name: '마법약 처방받기' }))
  await screen.findByText('오늘 밤의 처방')
  expect(screen.queryByRole('textbox')).toBeNull()
  await user.click(screen.getByRole('button', { name: '이야기로 돌아가기' }))
  expect(screen.getByText('오늘의 답변')).toBeTruthy()
  expect(screen.getByRole('textbox').value).toBe('이어서 할 이야기')
  expect(auth.logout).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: '이야기 건네기' }))
  await screen.findByText('오늘의 답변')
  expect(fetchMock.mock.calls.filter(([path]) => path === '/api/chat')).toHaveLength(2)
  await user.click(screen.getByRole('button', { name: '마법약 처방받기' }))
  await screen.findByText('오늘 밤의 처방')
  expect(fetchMock.mock.calls.filter(([path]) => path === '/api/prescription')).toHaveLength(2)
})

test('기록 선택·오래된 순서·한국 시간·닫기 후 현재 대화와 입력 보존', async () => {
  const user = userEvent.setup()
  render(<InteriorScene auth={auth} />)
  await send(user)
  await user.type(screen.getByRole('textbox'), '작성 중인 이야기')
  const dialog = await openHistory(user)
  expect(document.body.style.overflow).toBe('hidden')
  const day = within(dialog).getByRole('button', { name: /10월 8일/ })
  expect(day.parentElement.className).toContain('recorded')
  await user.click(day)
  await screen.findByRole('heading', { name: '2026-10-08의 이야기' })
  const records = screen.getByRole('list', { name: '이날 나눈 대화' })
  expect(records.textContent.indexOf('첫 번째 기록')).toBeLessThan(records.textContent.indexOf('두 번째 기록'))
  expect(within(records).getAllByText('00:00')).toHaveLength(2)
  expect(within(dialog).queryByRole('textbox')).toBeNull()
  await user.click(screen.getByRole('button', { name: '날짜 선택으로 돌아가기' }))
  await waitFor(() => expect(document.activeElement).toBe(day))
  fireEvent(dialog, new Event('cancel', { bubbles: false, cancelable: true }))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(document.body.style.overflow).toBe('')
  expect(document.activeElement).toBe(screen.getByRole('button', { name: '대화 기록', exact: true }))
  expect(screen.getByRole('textbox').value).toBe('작성 중인 이야기')
  expect(screen.getByText('오늘의 답변')).toBeTruthy()
})

test('월 이동과 기록 없는 날짜 선택', async () => {
  const user = userEvent.setup()
  render(<InteriorScene auth={auth} />)
  const dialog = await openHistory(user)
  await user.click(within(dialog).getByRole('button', { name: /10월 9일/ }))
  expect(screen.getByText('이날은 남겨진 이야기가 없어요.')).toBeTruthy()
  expect(screen.queryByRole('list', { name: '이날 나눈 대화' })).toBeNull()
  await user.click(within(dialog).getByRole('button', { name: '다음 달' }))
  expect(within(dialog).getByText('2026년 11월')).toBeTruthy()
  await user.click(within(dialog).getByRole('button', { name: '이전 달' }))
  expect(within(dialog).getByText('2026년 10월')).toBeTruthy()
})

test('빈 기록과 조회 실패 재시도', async () => {
  const user = userEvent.setup()
  fetchMock.mockImplementationOnce(() => response({}, 500))
  render(<InteriorScene auth={auth} />)
  await user.click(screen.getByRole('button', { name: '대화 기록', exact: true }))
  await screen.findByText('지난 이야기를 불러오지 못했어요. 잠시 후 다시 시도해주세요.')
  fetchMock.mockImplementationOnce(() => response({ chats: [] }))
  await user.click(screen.getByRole('button', { name: '다시 불러오기' }))
  await screen.findByText('아직 남겨진 이야기가 없어요.')
})

test.each([
  [400, '입력 내용을 확인해주세요. 이야기는 1~2000자로 보내주세요.'],
  [500, '대화를 저장하지 못했어요. 잠시 후 다시 시도해주세요.'],
  [502, '약방 주인이 답변을 받지 못했어요. 잠시 후 다시 시도해주세요.'],
  [504, '답변이 늦어지고 있어요. 잠시 후 다시 시도해주세요.'],
])('HTTP %s 오류 후 입력과 기존 답변 보존', async (status, message) => {
  const user = userEvent.setup()
  render(<InteriorScene auth={auth} />)
  await send(user)
  fetchMock.mockImplementationOnce(() => response({ detail: 'private-internal-detail' }, status))
  await user.type(screen.getByRole('textbox'), '실패할 질문')
  await user.click(screen.getByRole('button', { name: '이야기 건네기' }))
  await screen.findByText(message)
  expect(screen.getByRole('textbox').value).toBe('실패할 질문')
  expect(screen.getByText('오늘의 답변')).toBeTruthy()
  expect(document.body.textContent).not.toContain('private-internal-detail')
})

test('빈 입력·공백·길이 초과를 전송하지 않음', async () => {
  const user = userEvent.setup()
  render(<InteriorScene auth={auth} />)
  expect(screen.getByRole('button', { name: '이야기 건네기' }).disabled).toBe(true)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '   ' } })
  expect(screen.getByRole('button', { name: '이야기 건네기' }).disabled).toBe(true)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: '가'.repeat(2001) } })
  await user.click(screen.getByRole('button', { name: '이야기 건네기' }))
  expect(screen.getByText('이야기를 1~2000자로 입력해주세요.')).toBeTruthy()
  expect(fetchMock).not.toHaveBeenCalled()
})

test.each(['/api/chat', '/api/me/chats'])('%s 세션 만료를 인증 상태에 전달', async path => {
  const user = userEvent.setup()
  fetchMock.mockImplementationOnce(() => response({}, 401))
  render(<InteriorScene auth={auth} />)
  if (path === '/api/chat') {
    await user.type(screen.getByRole('textbox'), '질문')
    await user.click(screen.getByRole('button', { name: '이야기 건네기' }))
  } else await user.click(screen.getByRole('button', { name: '대화 기록', exact: true }))
  await waitFor(() => expect(auth.expire).toHaveBeenCalledOnce())
})

test('복원된 로그인에서 기록을 다시 조회하고 다른 사용자는 이전 기록을 보지 않음', async () => {
  const user = userEvent.setup()
  const view = render(<App />)
  await screen.findByRole('button', { name: '대화 기록', exact: true })
  await openHistory(user)
  view.unmount()
  auth.user = { id: 2, username: 'another_user' }
  fetchMock.mockImplementation(path => path === '/api/auth/me' ? response(auth.user) : response({ chats: [] }))
  render(<App />)
  await screen.findByRole('button', { name: '대화 기록', exact: true })
  await user.click(screen.getByRole('button', { name: '대화 기록', exact: true }))
  await screen.findByText('아직 남겨진 이야기가 없어요.')
  expect(screen.queryByText('첫 번째 기록')).toBeNull()
})

test('조회 중 닫으면 요청을 취소하고 다시 열 때 최신 기록을 요청', async () => {
  const user = userEvent.setup()
  let signal
  fetchMock.mockImplementationOnce((_, options) => { signal = options.signal; return new Promise(() => {}) })
  render(<InteriorScene auth={auth} />)
  await user.click(screen.getByRole('button', { name: '대화 기록', exact: true }))
  await screen.findByText('지난 이야기를 불러오고 있어요…')
  await user.click(screen.getByRole('button', { name: '대화 기록 닫기' }))
  expect(signal.aborted).toBe(true)
  await openHistory(user)
  expect(fetchMock.mock.calls.filter(([path]) => path === '/api/me/chats')).toHaveLength(2)
})

test('기록 조회 401 후 로그인 화면으로 이동하고 모달·스크롤 잠금 정리', async () => {
  const user = userEvent.setup()
  fetchMock.mockImplementation(path => path === '/api/auth/me' ? response(auth.user) : response({}, 401))
  render(<App />)
  await screen.findByRole('button', { name: '대화 기록', exact: true })
  await user.click(screen.getByRole('button', { name: '대화 기록', exact: true }))
  await screen.findByText('로그인이 만료됐어요. 다시 로그인해주세요.')
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(document.body.style.overflow).toBe('')
  expect(screen.queryByRole('button', { name: '대화 기록', exact: true })).toBeNull()
})

test('기록에 포함된 HTML을 실행하지 않고 텍스트로 표시', async () => {
  const user = userEvent.setup()
  const unsafe = '<img src=x onerror=alert(1)>'
  fetchMock.mockImplementationOnce(() => response({ chats: [{ ...current, question: unsafe }] }))
  render(<InteriorScene auth={auth} />)
  const dialog = await openHistory(user)
  await user.click(within(dialog).getByRole('button', { name: /10월 8일/ }))
  expect(screen.getByText(unsafe)).toBeTruthy()
  expect(within(dialog).queryByRole('img')).toBeNull()
})

test('기록을 읽는 동안 새 대화 저장으로 재조회가 실패해도 오류와 재시도 표시', async () => {
  const user = userEvent.setup()
  // A chat can finish while the user is reading the history dialog.
  let finishChat
  fetchMock.mockImplementationOnce(() => new Promise(resolve => { finishChat = resolve }))
  render(<InteriorScene auth={auth} />)
  await user.type(screen.getByRole('textbox'), '새 질문')
  await user.click(screen.getByRole('button', { name: '이야기 건네기' }))
  const dialog = await openHistory(user)
  await user.click(within(dialog).getByRole('button', { name: /10월 8일/ }))
  fetchMock.mockImplementationOnce(() => response({}, 500))
  finishChat({ ok: true, status: 200, json: async () => current })
  await screen.findByText('지난 이야기를 불러오지 못했어요. 잠시 후 다시 시도해주세요.')
  expect(screen.getByRole('button', { name: '다시 불러오기' })).toBeTruthy()
  await user.click(screen.getByRole('button', { name: '다시 불러오기' }))
  await screen.findByRole('list', { name: '이날 나눈 대화' })
})
