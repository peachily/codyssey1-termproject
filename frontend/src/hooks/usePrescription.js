import { useCallback, useEffect, useRef, useState } from 'react'
import { requestPrescription } from '../services/api.js'

function describeError(error) {
  switch (error.status) {
    case 400: return '마법약을 만들려면 먼저 이야기를 조금 들려주세요.'
    case 401: return '로그인이 만료됐어요. 다시 로그인해주세요.'
    case 500: return '서버에서 처방을 처리하지 못했어요. 잠시 후 다시 시도해주세요.'
    case 502: return '마법약을 위한 답변을 받지 못했어요. 잠시 후 다시 시도해주세요.'
    case 504: return '마법약을 만드는 데 시간이 걸리고 있어요. 잠시 후 다시 시도해주세요.'
    case 200: return '처방 결과를 확인할 수 없어요. 잠시 후 다시 시도해주세요.'
    default: return '처방 서비스에 연결할 수 없어요. 연결 상태를 확인해주세요.'
  }
}

export default function usePrescription(onExpired) {
  const [result, setResult] = useState(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const active = useRef(null)
  useEffect(() => () => { active.current?.abort(); active.current = null }, [])

  const request = useCallback(async () => {
    if (active.current || result) return
    const controller = new AbortController()
    active.current = controller
    setPending(true)
    setError('')
    try {
      const data = await requestPrescription(controller.signal)
      if (!controller.signal.aborted) setResult(data)
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError(describeError(failure))
        if (failure.status === 401) onExpired()
      }
    } finally {
      if (active.current === controller) { active.current = null; setPending(false) }
    }
  }, [onExpired, result])
  const dismiss = useCallback(() => { setResult(null); setError('') }, [])
  return { result, pending, error, request, dismiss }
}
