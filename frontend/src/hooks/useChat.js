import { useCallback, useEffect, useRef, useState } from 'react'
import { sendChat } from '../services/api.js'

function describeError(error) {
  switch (error.status) {
    case 400: return '입력 내용을 확인해주세요. 이야기는 1~2000자로 보내주세요.'
    case 401: return '로그인이 만료됐어요. 다시 로그인해주세요.'
    case 500: return '대화를 저장하지 못했어요. 잠시 후 다시 시도해주세요.'
    case 502: return '약방 주인이 답변을 받지 못했어요. 잠시 후 다시 시도해주세요.'
    case 504: return '답변이 늦어지고 있어요. 잠시 후 다시 시도해주세요.'
    case 404: return '대화 서비스에 연결할 수 없어요.'
    default: return '응답을 확인하지 못했어요. 연결 상태를 확인해주세요. 전송한 대화는 저장됐을 수 있어요.'
  }
}

export default function useChat(onExpired) {
  const [message, setMessage] = useState(null)
  const [lastChatId, setLastChatId] = useState(null)
  const [hasSuccessfulChat, setHasSuccessfulChat] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const active = useRef(null)
  const messageRef = useRef(null)

  useEffect(() => () => { active.current?.abort(); active.current = null }, [])

  const send = useCallback(async (value) => {
    if (active.current) return false
    const message = value.trim()
    if (!message || [...message].length > 2000) {
      setError('이야기를 1~2000자로 입력해주세요.')
      return false
    }
    const previousMessage = messageRef.current
    const controller = new AbortController()
    active.current = controller
    setMessage({ role: 'user', content: message })
    setPending(true)
    setError('')
    try {
      const reply = await sendChat(message, controller.signal)
      if (controller.signal.aborted) return false
      messageRef.current = { role: 'assistant', content: reply.answer }
      setMessage(messageRef.current)
      setHasSuccessfulChat(true)
      setLastChatId(reply.id)
      return true
    } catch (failure) {
      if (controller.signal.aborted) return false
      setMessage(previousMessage)
      setError(describeError(failure))
      if (failure.status === 401) onExpired()
      return false
    } finally {
      if (active.current === controller) {
        active.current = null
        setPending(false)
      }
    }
  }, [onExpired])

  return { message, lastChatId, hasSuccessfulChat, pending, error, send }
}
