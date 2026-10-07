import { useEffect, useRef } from 'react'
import usePrescription from '../hooks/usePrescription.js'
import PrescriptionResult from '../components/prescription/PrescriptionResult.jsx'
import useChat from '../hooks/useChat.js'
import ChatBubble from '../components/chat/ChatBubble.jsx'
import ChatInput from '../components/chat/ChatInput.jsx'
import ChatStatus from '../components/chat/ChatStatus.jsx'
import Owl from '../components/owl/Owl.jsx'
import AmbientGlow from '../components/scene/AmbientGlow.jsx'
import DustParticles from '../components/scene/DustParticles.jsx'
import SceneCanvas from '../components/scene/SceneCanvas.jsx'
import shopInterior from '../assets/backgrounds/shop-interior.webp'
import styles from './InteriorScene.module.css'

export default function InteriorScene({ auth }) {
  const chat = useChat(auth.expire)
  const prescription = usePrescription(auth.expire)
  const requestLock = useRef(false)
  const busy = chat.pending || prescription.pending || auth.pending
  const titleRef = useRef(null)
  const replyRef = useRef(null)
  useEffect(() => { titleRef.current?.focus() }, [])
  useEffect(() => { if (replyRef.current) replyRef.current.scrollTop = 0 }, [chat.message])

  async function sendMessage(message) {
    if (requestLock.current || busy || prescription.result) return false
    requestLock.current = true
    try { return await chat.send(message) } finally { requestLock.current = false }
  }

  async function prescribe() {
    if (requestLock.current || busy || !chat.hasSuccessfulChat || prescription.result) return
    requestLock.current = true
    try { await prescription.request() } finally { requestLock.current = false }
  }

  return <main className={styles.scene}>
    <SceneCanvas background={shopInterior}>
      <AmbientGlow /><DustParticles />
      {!prescription.result && <Owl />}
    </SceneCanvas>
    {prescription.result ? <div className={styles.prescriptionView}>
      <PrescriptionResult result={prescription.result} onExit={auth.logout} exiting={auth.pending} error={auth.error} />
    </div> : <>
      <header className={styles.controls}>
        <h1 ref={titleRef} tabIndex={-1} className={styles.title}>
          {auth.user.username}님, 약방에 잘 오셨어요.
          <span>오늘은 까무룩 잠들 수 있도록 도와드릴게요.</span>
        </h1>
        <button type="button" disabled={auth.pending} onClick={auth.logout}>{auth.pending ? '나가는 중…' : '나가기'}</button>
        {auth.error && <p role="alert">{auth.error}</p>}
      </header>
      <section className={styles.dialogue} aria-label="약방 주인과 대화">
        <div className={styles.response}>
          <div className={styles.current} ref={replyRef} tabIndex={chat.message ? 0 : undefined}
            role="region" aria-label="현재 이야기" aria-live="polite" aria-atomic="true">
            {chat.message && <ChatBubble message={chat.message} />}
          </div>
          <ChatStatus pending={chat.pending} error={chat.error} />
          {chat.message?.role === 'assistant' && <>
            <button type="button" className={styles.prescription} disabled={busy} onClick={prescribe}>
              {prescription.pending ? '마법약을 만들고 있어요…' : '마법약 처방받기'}
            </button>
            <ChatStatus error={prescription.error} />
          </>}
        </div>
        <ChatInput pending={busy} onSend={sendMessage} />
      </section>
    </>}
  </main>
}
