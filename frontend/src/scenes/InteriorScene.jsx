import usePrescription from '../hooks/usePrescription.js'
import PrescriptionResult from '../components/prescription/PrescriptionResult.jsx'
import useChat from '../hooks/useChat.js'
import { useEffect, useRef } from 'react'
import ChatBubble from '../components/chat/ChatBubble.jsx'
import ChatInput from '../components/chat/ChatInput.jsx'
import ChatStatus from '../components/chat/ChatStatus.jsx'
import Owl from '../components/owl/Owl.jsx'
import AmbientGlow from '../components/scene/AmbientGlow.jsx'
import DustParticles from '../components/scene/DustParticles.jsx'
import SceneCanvas from '../components/scene/SceneCanvas.jsx'
import shopInterior from '../assets/backgrounds/shop-interior.png'
import styles from './InteriorScene.module.css'

export default function InteriorScene({ auth }) {
  const chat = useChat(auth.expire)
  const prescription = usePrescription(auth.expire)
  const requestLock = useRef(false)
  const hasSuccessfulChat = chat.messages.some((message) => message.role === 'assistant')
  const busy = chat.pending || prescription.pending || auth.pending

  async function sendMessage(message) {
    if (requestLock.current || busy || prescription.result) return false
    requestLock.current = true
    try { return await chat.send(message) } finally { requestLock.current = false }
  }

  async function prescribe() {
    if (requestLock.current || busy || !hasSuccessfulChat || prescription.result) return
    requestLock.current = true
    try { await prescription.request() } finally { requestLock.current = false }
  }
  const logRef = useRef(null)
  const followRef = useRef(true)
  useEffect(() => {
    if (followRef.current && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [chat.messages, chat.pending])
  const titleRef = useRef(null)
  useEffect(() => { titleRef.current?.focus() }, [])

  return (
    <main className={styles.scene}>
      <SceneCanvas background={shopInterior}><AmbientGlow /><DustParticles /><Owl /></SceneCanvas>
      <section className={styles.controls} aria-label="약방">
        <h1 ref={titleRef} tabIndex={-1} className={styles.title}>까무룩 약방</h1>
        <p>{auth.user.username}님, 어서 오세요.</p>
        <button type="button" disabled={auth.pending} onClick={auth.logout}>
          {auth.pending ? '나가는 중…' : '로그아웃'}
        </button>
        <p role="alert">{auth.error}</p>
      </section>
      <section className={styles.dialogue} aria-label={prescription.result ? '마법약 처방' : '올빼미와 대화'}>
        {prescription.result ? <PrescriptionResult result={prescription.result} /> : <>
        <ol className={styles.messages} ref={logRef} role="log" aria-label="이번 대화" aria-live="polite" aria-relevant="additions text"
          tabIndex={0} onScroll={(event) => {
            const list = event.currentTarget
            followRef.current = list.scrollHeight - list.scrollTop - list.clientHeight < 32
          }}>
          {chat.messages.map((message) => <ChatBubble key={message.id} message={message} />)}
        </ol>
        <ChatStatus pending={chat.pending} error={chat.error} />
        <ChatInput pending={busy} onSend={sendMessage} />
        <button type="button" className={styles.prescription} disabled={busy || !hasSuccessfulChat}
          onClick={prescribe} aria-describedby="prescription-note">
          {prescription.pending ? '마법약을 만들고 있어요…' : '마법약 처방받기'}
        </button>
        <p role="status" className={styles.note}>{prescription.pending ? '이야기를 담은 마법약을 준비하고 있어요.' : ''}</p>
        <ChatStatus error={prescription.error} />
        <p id="prescription-note" className={styles.note}>{!hasSuccessfulChat ? '먼저 올빼미에게 이야기를 들려주세요.' : ''}</p>
        </>}
      </section>
    </main>
  )
}
