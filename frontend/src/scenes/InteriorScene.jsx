import { useEffect, useRef } from 'react'
import SceneCanvas from '../components/scene/SceneCanvas.jsx'
import shopInterior from '../assets/backgrounds/shop-interior.png'
import styles from './InteriorScene.module.css'

export default function InteriorScene({ auth }) {
  const titleRef = useRef(null)
  useEffect(() => { titleRef.current?.focus() }, [])

  return (
    <main className={styles.scene}>
      <SceneCanvas background={shopInterior} />
      <section className={styles.controls} aria-label="약방">
        <h1 ref={titleRef} tabIndex={-1} className={styles.title}>까무룩 약방</h1>
        <p>{auth.user.username}님, 어서 오세요.</p>
        <button type="button" disabled={auth.pending} onClick={auth.logout}>
          {auth.pending ? '나가는 중…' : '로그아웃'}
        </button>
        <p role="alert">{auth.error}</p>
      </section>
    </main>
  )
}
