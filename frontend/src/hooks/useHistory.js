import { useEffect, useState } from 'react'
import { getChats } from '../services/api.js'

export default function useHistory(open, revision, onExpired) {
  const [state, setState] = useState({ chats: [], pending: true, error: '' })
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    setState({ chats: [], pending: true, error: '' })
    getChats(controller.signal).then(chats => {
      if (!controller.signal.aborted) setState({ chats, pending: false, error: '' })
    }).catch(error => {
      if (controller.signal.aborted) return
      if (error.status === 401) onExpired()
      else setState({ chats: [], pending: false, error: '지난 이야기를 불러오지 못했어요. 잠시 후 다시 시도해주세요.' })
    })
    return () => controller.abort()
  }, [open, revision, retry, onExpired])
  return { ...state, reload: () => setRetry(value => value + 1) }
}
