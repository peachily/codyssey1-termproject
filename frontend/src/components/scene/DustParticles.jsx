import styles from './DustParticles.module.css'
const particles = [[18, 35, -2], [28, 59, -7], [39, 42, -11], [48, 28, -5], [57, 54, -14], [65, 36, -9], [74, 60, -3], [82, 43, -12], [44, 66, -16]]
export default function DustParticles() {
  return <div className={styles.dust} aria-hidden="true">{particles.map(([x, y, delay], index) => (
    <i key={index} style={{ left: `${x}%`, top: `${y}%`, animationDelay: `${delay}s` }} />
  ))}</div>
}
