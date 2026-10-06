import SceneCanvas from '../components/scene/SceneCanvas.jsx'
import shopExterior from '../assets/backgrounds/shop-exterior.png'
import styles from './EntranceScene.module.css'

export default function EntranceScene({ status }) {
  return (
    <main className={styles.scene}>
      <SceneCanvas background={shopExterior}>
        <h1 className={styles.sign}>까무룩</h1>
      </SceneCanvas>
      <p className={styles.status} role="status">{status}</p>
    </main>
  )
}
