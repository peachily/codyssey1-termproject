import { useEffect, useId, useRef } from 'react'
import PotionBottle from './PotionBottle.jsx'
import styles from './PrescriptionResult.module.css'

export default function PrescriptionResult({ result }) {
  const titleRef = useRef(null)
  const id = useId()
  useEffect(() => { titleRef.current?.focus() }, [])
  return <section className={styles.result} aria-labelledby={id}>
    <PotionBottle color={result.color} />
    <div className={styles.paper}>
      <h2 id={id} ref={titleRef} tabIndex={-1}>오늘 밤의 처방</h2>
      <p>{result.message}</p>
    </div>
  </section>
}
