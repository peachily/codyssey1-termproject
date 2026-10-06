import styles from './ChatStatus.module.css'
export default function ChatStatus({ pending = false, error = '' }) {
  return <div className={styles.status}>
    <p role="status">{pending ? '올빼미가 이야기를 듣고 있어요…' : ''}</p>
    <p role="alert" className={styles.error}>{error}</p>
  </div>
}
