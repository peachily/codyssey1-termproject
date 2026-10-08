import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { DayPicker } from 'react-day-picker'
import { ko } from 'react-day-picker/locale'
import 'react-day-picker/style.css'
import useHistory from '../../hooks/useHistory.js'
import { groupChats, historyDate, historyTime, HISTORY_TIME_ZONE } from './historyDates.js'
import styles from './HistoryPanel.module.css'

export default function HistoryPanel({ revision, onExpired }) {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState()
  const dialogRef = useRef(null)
  const triggerRef = useRef(null)
  const titleRef = useRef(null)
  const dayRef = useRef(null)
  const [reading, setReading] = useState(false)
  const title = useId()
  const history = useHistory(open, revision, onExpired)
  const showRecords = reading && !history.pending && !history.error
  const groups = useMemo(() => groupChats(history.chats), [history.chats])

  useEffect(() => {
    if (!open) return
    const dialog = dialogRef.current
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialog.showModal()
    return () => {
      dialog.close()
      document.body.style.overflow = overflow
      triggerRef.current?.focus()
    }
  }, [open])

  useEffect(() => {
    if (showRecords) titleRef.current?.focus()
  }, [showRecords])

  function selectDay(date) {
    setSelected(date)
    if (date && groups.has(historyDate(date))) {
      dayRef.current = document.activeElement
      setReading(true)
    }
  }

  function back() {
    setReading(false)
    requestAnimationFrame(() => dayRef.current?.focus())
  }
  function close() { setOpen(false); setSelected(undefined); setReading(false) }

  return <>
    <button ref={triggerRef} type="button" aria-label="대화 기록" title="지난 이야기"
      aria-haspopup="dialog" onClick={() => setOpen(true)}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
        <rect x="3" y="5" width="18" height="16" rx="3" />
        <path d="M7 3v4M17 3v4M3 11h18M7 15h2M11 15h2M15 15h2M7 18h2M11 18h2" />
      </svg>
    </button>
    {open && createPortal(<dialog ref={dialogRef} className={`${styles.dialog} ${reading ? styles.reading : ""}`} aria-labelledby={title}
      onCancel={event => { event.preventDefault(); close() }}>
      <header className={styles.header}>
        {reading && <button className={styles.iconButton} type="button" onClick={back} aria-label="날짜 선택으로 돌아가기"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="m15 5-7 7 7 7" /></svg></button>}
        <h2 id={title} ref={titleRef} tabIndex={-1}>{reading && selected ? `${historyDate(selected)}의 이야기` : '지난 이야기'}</h2>
        <button className={styles.iconButton} type="button" onClick={close} aria-label="대화 기록 닫기" autoFocus><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button>
      </header>
      <div className={styles.content} hidden={showRecords}>
        {history.pending ? <p role="status">지난 이야기를 불러오고 있어요…</p> : history.error ? <>
          <p role="alert">{history.error}</p><button type="button" onClick={history.reload}>다시 불러오기</button>
        </> : <>
          <DayPicker mode="single" locale={ko} timeZone={HISTORY_TIME_ZONE}
            selected={selected} onSelect={selectDay}
            modifiers={{ recorded: date => groups.has(historyDate(date)) }}
            modifiersClassNames={{ recorded: styles.recorded }}
            labels={{ labelPrevious: () => '이전 달', labelNext: () => '다음 달' }} />
          {!history.chats.length && <p role="status">아직 남겨진 이야기가 없어요.</p>}
          {selected && history.chats.length > 0 && !groups.has(historyDate(selected)) &&
            <p role="status">이날은 남겨진 이야기가 없어요.</p>}
        </>}
      </div>
      {showRecords && selected && <ol className={styles.messages} aria-label="이날 나눈 대화" tabIndex={0}>
        {(groups.get(historyDate(selected)) || []).map(chat => <li key={chat.id} className={styles.exchange}>
          <article className={styles.question} aria-label="내 이야기">
            <span className={styles.speaker}>나</span><p>{chat.question}</p>
            <time dateTime={chat.created_at}>{historyTime(chat.created_at)}</time>
          </article>
          <article className={styles.answer} aria-label="약방 주인의 답변">
            <span className={styles.speaker}>약방 주인</span><p>{chat.answer}</p>
            <time dateTime={chat.created_at}>{historyTime(chat.created_at)}</time>
          </article>
        </li>)}
      </ol>}
    </dialog>, document.body)}
  </>
}
