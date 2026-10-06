import styles from './SceneCanvas.module.css'

export default function SceneCanvas({ background, children, motionClassName = '' }) {
  return (
    <div className={styles.viewport}>
      <div className={styles.artboard}>
        <div className={`${styles.motion} ${motionClassName}`}>
          <img
            className={styles.background}
            src={background}
            alt=""
            width="1672"
            height="941"
            fetchPriority="high"
            draggable="false"
          />
          {children}
        </div>
      </div>
    </div>
  )
}
