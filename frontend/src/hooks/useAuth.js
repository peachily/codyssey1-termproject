import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../services/api.js'

function errorMessage(error) {
  if (error.status === 404) return '인증 서비스에 연결할 수 없어요. 잠시 후 다시 시도해주세요.'
  if (error.status === 401) return '아이디와 비밀번호를 확인해주세요.'
  if (error.status === 409) return '이미 사용 중인 아이디예요.'
  if (error.status === 400) return '입력한 아이디와 비밀번호를 확인해주세요.'
  if (error.status >= 500) return '서버에서 요청을 처리하지 못했어요. 잠시 후 다시 시도해주세요.'
  return '연결을 확인하고 다시 시도해주세요.'
}

export default function useAuth() {
  const [session, setSession] = useState({ phase: 'checking', user: null, source: null })
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const active = useRef(null)

  const clearFeedback = useCallback(() => { setError(''); setNotice('') }, [])

  const expire = useCallback(() => {
    active.current?.abort()
    active.current = null
    setPending(false)
    setSession({ phase: 'anonymous', user: null, source: null })
    setError('로그인이 만료됐어요. 다시 로그인해주세요.')
    setNotice('')
  }, [])

  const checkSession = useCallback(async () => {
    if (active.current) return
    const controller = new AbortController()
    active.current = controller
    setSession({ phase: 'checking', user: null, source: null })
    setError('')
    try {
      const user = await api.getMe(controller.signal)
      if (!controller.signal.aborted) setSession({ phase: 'authenticated', user, source: 'restored' })
    } catch (failure) {
      if (controller.signal.aborted) return
      if (failure.status === 401) {
        setSession({ phase: 'anonymous', user: null, source: null })
      } else {
        setSession({ phase: 'error', user: null, source: null })
        setError(errorMessage(failure))
      }
    } finally {
      if (active.current === controller) active.current = null
    }
  }, [])

  useEffect(() => {
    checkSession()
    return () => { active.current?.abort(); active.current = null }
  }, [checkSession])

  const perform = useCallback(async (kind, credentials) => {
    if (active.current) return false
    const controller = new AbortController()
    active.current = controller
    setPending(true)
    clearFeedback()
    try {
      if (kind === 'signup') {
        await api.signup(credentials, controller.signal)
        if (controller.signal.aborted) return false
        setNotice('가입이 완료됐어요. 로그인하고 약방에 들어와주세요.')
      } else if (kind === 'login') {
        const user = await api.login(credentials, controller.signal)
        if (controller.signal.aborted) return false
        setSession({ phase: 'authenticated', user, source: 'login' })
      } else if (kind === 'logout') {
        await api.logout(controller.signal)
        if (controller.signal.aborted) return false
        setSession({ phase: 'anonymous', user: null, source: null })
      } else {
        return false
      }
      return true
    } catch (failure) {
      if (!controller.signal.aborted) setError(errorMessage(failure))
      return false
    } finally {
      if (active.current === controller) {
        active.current = null
        setPending(false)
      }
    }
  }, [clearFeedback])

  return { ...session, pending: pending || session.phase === 'checking', error, notice,
    submit: perform, logout: () => perform('logout'), retry: checkSession, clearFeedback, expire }
}
