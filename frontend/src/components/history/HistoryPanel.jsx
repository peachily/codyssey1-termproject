import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { DayPicker } from 'react-day-picker'
import { ko } from 'react-day-picker/locale'
import 'react-day-picker/style.css'
import useHistory from '../../hooks/useHistory.js'
import { groupChats, historyDate, HISTORY_TIME_ZONE } from './historyDates.js'
import styles from './HistoryPanel.module.css'

export default function HistoryPanel({ revision, onExpired }) {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState()
  const dialogRef = useRef(null)
  const triggerRef = useRef(null)
  const title = useId()
  const history = useHistory(open, revision, onExpired)
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

  function close() { setOpen(false); setSelected(undefined) }

  return <>
    <button ref={triggerRef} type="button" aria-label="대화 기록" title="지난 이야기"
      aria-haspopup="dialog" onClick={() => setOpen(true)}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
        <rect x="3" y="5" width="18" height="16" rx="3" />
        <path d="M7 3v4M17 3v4M3 11h18M7 15h2M11 15h2M15 15h2M7 18h2M11 18h2" />
      </svg>
    </button>
    {open && createPortal(<dialog ref={dialogRef} className={styles.dialog} aria-labelledby={title}
      onCancel={event => { event.preventDefault(); close() }}>
      <header className={styles.header}>
        <h2 id={title}>지난 이야기</h2>
        <button type="button" onClick={close} aria-label="대화 기록 닫기" autoFocus>닫기</button>
      </header>
      <div className={styles.content}>
        {history.pending ? <p role="status">지난 이야기를 불러오고 있어요…</p> : history.error ? <>
          <p role="alert">{history.error}</p><button type="button" onClick={history.reload}>다시 불러오기</button>
        </> : <>
          <DayPicker mode="single" locale={ko} timeZone={HISTORY_TIME_ZONE}
            selected={selected} onSelect={setSelected}
            modifiers={{ recorded: date => groups.has(historyDate(date)) }}
            modifiersClassNames={{ recorded: styles.recorded }}
            labels={{ labelPrevious: () => '이전 달', labelNext: () => '다음 달' }} />
          <p role="status">{selected
            ? groups.has(historyDate(selected)) ? '이날 나눈 이야기가 있어요.' : '이날은 남겨진 이야기가 없어요.'
            : history.chats.length ? '은은하게 표시된 날의 이야기를 펼쳐보세요.' : '아직 남겨진 이야기가 없어요.'}</p>
          <p className={styles.note}>날짜와 시간은 한국 시간을 기준으로 표시해요.</p>
        </>}
      </div>
    </dialog>, document.body)}
  </>
}
