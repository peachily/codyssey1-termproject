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
      <div className={styles.auth}><AuthPanel {...auth} /></div>
      <p className={styles.status} role="status">{status}</p>
    </main>
  )
}
