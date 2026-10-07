import { useEffect } from 'react'
import AuthPanel from '../components/auth/AuthPanel.jsx'
import SceneCanvas from '../components/scene/SceneCanvas.jsx'
import shopExterior from '../assets/backgrounds/shop-exterior.png'
import styles from './EntranceScene.module.css'

export default function EntranceScene({ status, auth, entering = false, onEntered }) {
  useEffect(() => {
    if (!entering) return
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const skipMotion = () => { if (preference.matches) onEntered() }
    skipMotion()
    preference.addEventListener('change', skipMotion)
    return () => preference.removeEventListener('change', skipMotion)
  }, [entering, onEntered])

  return (
    <main className={styles.scene} aria-busy={entering}>
      <SceneCanvas background={shopExterior} motionClassName={entering ? styles.entering : ''}>
        <h1 className={styles.sign}>까무룩</h1>
      </SceneCanvas>
      {!entering && (
        <div className={styles.auth}>
          <div className={styles.authContent}>
            <AuthPanel onSubmit={auth.submit} pending={auth.pending} error={auth.error}
              notice={auth.phase === 'checking' ? '로그인 상태를 확인하고 있어요…' : auth.notice}
              onModeChange={auth.clearFeedback} />
            {auth.phase === 'error' && <button type="button" disabled={auth.pending} onClick={auth.retry}>로그인 상태 다시 확인</button>}
          </div>
        </div>
      )}
      <p className={styles.status} role="status">{entering ? '약방에 들어가고 있어요…' : status}</p>
      {entering && <div className={styles.fade} aria-hidden="true" onAnimationEnd={(event) => {
        if (event.target === event.currentTarget) onEntered()
      }} />}
    </main>
  )
}
