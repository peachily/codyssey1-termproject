import styles from './ChatBubble.module.css'

export default function ChatBubble({ message }) {
  return <div className={styles.bubble}>
    <span className={styles.speaker}>{message.role === 'user' ? '나' : '약방 주인'}</span>
    <p>{message.content}</p>
  </div>
}
