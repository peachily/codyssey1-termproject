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

export default function InteriorScene({ auth, chat = { messages: [], pending: false, error: '' } }) {
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
      <section className={styles.dialogue} aria-label="올빼미와 대화">
        <ol className={styles.messages} ref={logRef} role="log" aria-label="이번 대화" aria-live="polite" aria-relevant="additions text"
          tabIndex={0} onScroll={(event) => {
            const list = event.currentTarget
            followRef.current = list.scrollHeight - list.scrollTop - list.clientHeight < 32
          }}>
          {chat.messages.map((message) => <ChatBubble key={message.id} message={message} />)}
        </ol>
        <ChatStatus pending={chat.pending} error={chat.error} />
        <ChatInput pending={chat.pending} onSend={chat.send} />
        <button type="button" className={styles.prescription} disabled aria-describedby="prescription-note">마법약 처방받기</button>
        <p id="prescription-note" className={styles.note}>처방 기능은 준비 중이에요.</p>
      </section>
    </main>
  )
}
