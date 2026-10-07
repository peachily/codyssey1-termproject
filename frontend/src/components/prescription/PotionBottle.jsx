import styles from './PotionBottle.module.css'

const colors = {
  BLUE: 'var(--potion-blue)',
  PURPLE: 'var(--potion-purple)',
  PINK: 'var(--potion-pink)',
  GREEN: 'var(--potion-green)',
  YELLOW: 'var(--potion-yellow)',
}

export default function PotionBottle({ color }) {
  if (!Object.hasOwn(colors, color)) return null
  return <div className={styles.bottle} role="img" aria-label="마법약 병" style={{ '--liquid-color': colors[color] }}>
    <div className={styles.stopper} />
    <div className={styles.neck} />
    <div className={styles.glass}><div className={styles.liquid} /><span className={styles.mark} aria-hidden="true">☾</span></div>
  </div>
}
