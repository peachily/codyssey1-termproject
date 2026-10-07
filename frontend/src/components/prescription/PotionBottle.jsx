import bottle from '../../assets/potions/potion-bottle.png'
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
    <div className={styles.liquidWindow} aria-hidden="true"><div className={styles.liquid} /></div>
    <img className={styles.shell} src={bottle} alt="" width="1312" height="1199" draggable="false" />
  </div>
}
