import { useCallback, useEffect, useState } from 'react'
import useAuth from './hooks/useAuth.js'
import InteriorScene from './scenes/InteriorScene.jsx'
import EntranceScene from './scenes/EntranceScene.jsx'

export default function App() {
  const auth = useAuth()
  const [entered, setEntered] = useState(false)
  const completeEntry = useCallback(() => setEntered(true), [])

  useEffect(() => { if (!auth.user) setEntered(false) }, [auth.user])
  if (auth.user && (auth.source === 'restored' || entered)) return <InteriorScene key={auth.user.id} auth={auth} />
  return <EntranceScene auth={auth}
    entering={auth.phase === 'authenticated' && auth.source === 'login'} onEntered={completeEntry} />
}
