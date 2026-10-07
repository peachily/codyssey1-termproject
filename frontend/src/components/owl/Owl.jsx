import owl from '../../assets/owl/owl-open.webp'
import styles from './Owl.module.css'

export default function Owl() {
  return <div className={styles.owl}><img src={owl} alt="약방 주인" width="1122" height="1402" draggable="false" /></div>
}
