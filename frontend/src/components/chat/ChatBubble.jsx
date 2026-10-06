import styles from './ChatBubble.module.css'
export default function ChatBubble({ message }) {
  return <li className={`${styles.bubble} ${message.role === 'user' ? styles.user : styles.owl}`}>
    <span className={styles.speaker}>{message.role === 'user' ? '나' : '올빼미'}</span>
    <p>{message.content}</p>
    {message.failed && <span className={styles.failed}>응답을 받지 못했어요.</span>}
  </li>
}
