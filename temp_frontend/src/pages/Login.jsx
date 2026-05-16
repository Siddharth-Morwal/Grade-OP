import { useState } from 'react';
import { useApp } from '../hooks/useApp';
import styles from './Login.module.css';

export default function Login() {
  const { login } = useApp();
  const [role, setRole] = useState('instructor');
  const [email, setEmail] = useState('instructor@gradeops.io');
  const [password, setPassword] = useState('demo1234');

  function pickRole(r) {
    setRole(r);
    setEmail(r === 'instructor' ? 'instructor@gradeops.io' : 'ta@gradeops.io');
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.bgGrid} aria-hidden />
      <div className={styles.card}>
        <div className={styles.logoRow}>
          <span className={styles.logoMark}>{'</>'}</span>
          <span className={styles.logoText}>GradeOps</span>
        </div>
        <p className={styles.tagline}>Human-in-the-Loop Grading System</p>

        <div className={styles.divider} />

        <p className={styles.fieldLabel}>Sign in as</p>
        <div className={styles.rolePicker}>
          <button
            className={`${styles.roleBtn} ${role === 'instructor' ? styles.roleBtnActive : ''}`}
            onClick={() => pickRole('instructor')}
          >
            <i className="ti ti-school" />
            <span className={styles.roleName}>Instructor</span>
            <span className={styles.roleDesc}>Upload exams · View results</span>
          </button>
          <button
            className={`${styles.roleBtn} ${role === 'ta' ? styles.roleBtnActive : ''}`}
            onClick={() => pickRole('ta')}
          >
            <i className="ti ti-user-check" />
            <span className={styles.roleName}>Teaching Assistant</span>
            <span className={styles.roleDesc}>Review · Approve · Override</span>
          </button>
        </div>

        <div className={styles.fields}>
          <div className={styles.formGroup}>
            <label className={styles.fieldLabel}>Email</label>
            <input
              className={styles.input}
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
          </div>
          <div className={styles.formGroup}>
            <label className={styles.fieldLabel}>Password</label>
            <input
              className={styles.input}
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
          </div>
        </div>

        <button className={styles.submitBtn} onClick={() => login(role)}>
          <i className="ti ti-arrow-right" />
          Sign In
        </button>
        <p className={styles.hint}>Demo — any password works</p>
      </div>
    </div>
  );
}
