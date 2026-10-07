import { useId, useRef, useState } from 'react'
import styles from './AuthPanel.module.css'

export default function AuthPanel({ onSubmit, pending = false, error = '', notice = '', onModeChange }) {
  const [mode, setMode] = useState('login')
  const [registered, setRegistered] = useState(false)
  const [validation, setValidation] = useState('')
  const formRef = useRef(null)
  const id = useId()
  const signup = mode === 'signup'

  async function submit(event) {
    event.preventDefault()
    if (pending || event.nativeEvent.isComposing) return
    const form = event.currentTarget
    const values = new FormData(form)
    const username = values.get('username').trim()
    const password = values.get('password')
    if (!/^[a-z0-9_]{3,30}$/.test(username)) {
      setValidation('아이디는 영문 소문자, 숫자, 밑줄로 3~30자 입력해주세요.')
      form.elements.username.focus()
      return
    }
    if (!/\S/u.test(password) || [...password].length < 8 || [...password].length > 128) {
      setValidation('비밀번호는 공백만 사용할 수 없으며 8~128자 입력해주세요.')
      form.elements.password.focus()
      return
    }
    setValidation('')
    if (!onSubmit) return
    const success = await onSubmit(mode, { username, password })
    if (success) {
      form.reset()
      if (signup) {
        setMode('login')
        setRegistered(true)
        form.elements.username.value = username
        form.elements.password.focus()
      }
    }
  }

  function switchMode() {
    onModeChange?.()
    setMode(registered ? 'login' : signup ? 'login' : 'signup')
    setRegistered(false)
    setValidation('')
    formRef.current.reset()
    formRef.current.elements.username.focus()
  }

  return (
    <section className={styles.panel} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className={styles.title}>{signup ? '처음 오셨나요?' : '까무룩 잠들고 싶은 밤,'}</h2>
      <p>{signup ? '작은 약방에 이름을 남겨주세요.' : '오늘의 마음을 잠시 내려놓고 가세요.'}</p>
      <form ref={formRef} onSubmit={submit} noValidate aria-busy={pending}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && (event.nativeEvent.isComposing || event.keyCode === 229)) event.preventDefault()
        }}>
        <fieldset className={styles.fields} disabled={pending}>
          <label htmlFor={`${id}-username`}>아이디</label>
          <input id={`${id}-username`} name="username" autoComplete="username" autoCapitalize="none"
            spellCheck={false} required aria-describedby={`${id}-feedback`} />
          <label htmlFor={`${id}-password`}>비밀번호</label>
          <input id={`${id}-password`} name="password" type="password"
            autoComplete={signup ? 'new-password' : 'current-password'} required aria-describedby={`${id}-feedback`} />
          <p id={`${id}-feedback`} className={styles.error} role="alert">{validation || error}</p>
          <p className={styles.notice} role="status">{notice}</p>
          {registered && <button className={styles.secondary} type="button" onClick={switchMode}>다른 이름으로 들어가기</button>}
          <button className={styles.primary} type="submit">{pending ? '확인하고 있어요…' : signup ? '가입하기' : '로그인'}</button>
          {!registered && <button className={styles.secondary} type="button" onClick={switchMode}>
            {signup ? '로그인으로 돌아가기' : '처음 방문하셨나요?'}
          </button>}
        </fieldset>
      </form>
    </section>
  )
}
