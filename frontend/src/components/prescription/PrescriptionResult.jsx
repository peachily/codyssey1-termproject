import { useEffect, useId, useRef } from 'react'
import PotionBottle from './PotionBottle.jsx'
import styles from './PrescriptionResult.module.css'

export default function PrescriptionResult({ result, onReturn }) {
  const titleRef = useRef(null)
  const id = useId()
  useEffect(() => { titleRef.current?.focus() }, [])
  return <section className={styles.result} aria-labelledby={id}>
    <h1 id={id} ref={titleRef} tabIndex={-1}>오늘 밤의 처방</h1>
    <PotionBottle color={result.color} />
    <p className={styles.message}>{result.message}</p>
    <button className={styles.exit} type="button" onClick={onReturn}>
      이야기로 돌아가기
    </button>
  </section>
}
