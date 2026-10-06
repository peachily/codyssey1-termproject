import AuthPanel from '../components/auth/AuthPanel.jsx'
import SceneCanvas from '../components/scene/SceneCanvas.jsx'
import shopExterior from '../assets/backgrounds/shop-exterior.png'
import styles from './EntranceScene.module.css'

export default function EntranceScene({ status, auth }) {
  return (
    <main className={styles.scene}>
      <SceneCanvas background={shopExterior}>
        <h1 className={styles.sign}>까무룩</h1>
      </SceneCanvas>
      <div className={styles.auth}>
        {auth?.user ? (
          <section className={styles.session} aria-label="로그인 상태">
            <p>{auth.user.username}님, 반가워요.</p>
            <button type="button" disabled={auth.pending} onClick={auth.logout}>로그아웃</button>
            <p role="alert">{auth.error}</p>
          </section>
        ) : (
          <div className={styles.authContent}>
            <AuthPanel onSubmit={auth?.submit} pending={auth?.pending} error={auth?.error}
              notice={auth?.phase === 'checking' ? '로그인 상태를 확인하고 있어요…' : auth?.notice}
              onModeChange={auth?.clearFeedback} />
            {auth?.phase === 'error' && <button type="button" disabled={auth.pending} onClick={auth.retry}>로그인 상태 다시 확인</button>}
          </div>
        )}
      </div>
      <p className={styles.status} role="status">{status}</p>
    </main>
  )
}
