import { useId, useRef, useState } from 'react'
import styles from './ChatInput.module.css'

export default function ChatInput({ onSend, pending = false }) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const id = useId()
  const inputRef = useRef(null)
  const composing = useRef(false)
  const sending = useRef(false)

  async function submit(event) {
    event.preventDefault()
    if (pending || sending.current || composing.current) return
    const message = draft.trim()
    if (!message || [...message].length > 2000) {
      setError('이야기를 1~2000자로 입력해주세요.')
      inputRef.current?.focus()
      return
    }
    setError('')
    if (!onSend) return
    sending.current = true
    try {
      if (await onSend(message)) setDraft('')
    } finally {
      sending.current = false
      if (document.activeElement === document.body || document.activeElement === inputRef.current) inputRef.current?.focus()
    }
  }

  return <form className={styles.form} onSubmit={submit} aria-busy={pending}>
    <label htmlFor={id}>오늘은 어떤 마음인가요?</label>
    <textarea id={id} ref={inputRef} value={draft} rows={2} readOnly={pending}
      aria-describedby={`${id}-hint ${id}-error`} enterKeyHint="send"
      onChange={(event) => { setDraft(event.target.value); setError('') }}
      onCompositionStart={() => { composing.current = true }}
      onCompositionEnd={() => { composing.current = false }}
      onKeyDown={(event) => {
        if (event.key !== 'Enter' || event.shiftKey) return
        if (composing.current || event.nativeEvent.isComposing || event.keyCode === 229) return
        event.preventDefault()
        event.currentTarget.form.requestSubmit()
      }} />
    <div className={styles.actions}>
      <span id={`${id}-hint`}>{[...draft.trim()].length}/2000 · Shift+Enter 줄바꿈</span>
      <button type="submit" disabled={pending}>{pending ? '듣는 중…' : '이야기 건네기'}</button>
    </div>
    <p id={`${id}-error`} role="alert" className={styles.error}>{error}</p>
  </form>
}
