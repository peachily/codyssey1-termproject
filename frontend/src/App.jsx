import { useEffect, useState } from 'react'
import EntranceScene from './scenes/EntranceScene.jsx'

export default function App() {
  const [status, setStatus] = useState('확인 중…')

  useEffect(() => {
    const controller = new AbortController()

    async function checkHealth() {
      try {
        const response = await fetch('/health', {
          credentials: 'include',
          signal: controller.signal,
        })
        if (!response.ok) throw new Error('Health request failed')
        const data = await response.json()
        if (data.status !== 'ok') throw new Error('Unexpected health response')
        setStatus('FastAPI 연결 성공')
      } catch (error) {
        if (error.name !== 'AbortError') {
          setStatus('FastAPI 연결 실패: 백엔드 실행 상태를 확인하세요.')
        }
      }
    }

    checkHealth()
    return () => controller.abort()
  }, [])

  return <EntranceScene status={status} />
}
