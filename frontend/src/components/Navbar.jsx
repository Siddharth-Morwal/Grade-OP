import { useApp } from '../hooks/useApp';
import styles from './Navbar.module.css';

const INSTRUCTOR_TABS = [
  { id: 'courses', icon: 'layout-grid', label: 'Courses' },
  { id: 'review',  icon: 'checkup-list',  label: 'Review Queue' },
  { id: 'results', icon: 'chart-bar',   label: 'Results' },
];
const TA_TABS = [
  { id: 'courses', icon: 'layout-grid',   label: 'Courses' },
  { id: 'upload',  icon: 'upload',      label: 'Upload' },
  { id: 'results', icon: 'chart-bar',     label: 'Results' },
];

export default function Navbar({ screen, onNav }) {
  const { user, logout } = useApp();
  if (!user) return null;

  const tabs = user.role === 'instructor' ? INSTRUCTOR_TABS : TA_TABS;

  return (
    <nav className={styles.nav}>
      <div className={styles.logo} onClick={() => onNav('courses')}>
        <span className={styles.logoMark}>{'</>'}</span>
        GradeOps
      </div>

      <div className={styles.tabs}>
        {tabs.map(t => (
          <button
            key={t.id}
            className={`${styles.tab} ${screen === t.id ? styles.tabActive : ''}`}
            onClick={() => onNav(t.id)}
          >
            <i className={`ti ti-${t.icon}`} />
            {t.label}
          </button>
        ))}
      </div>

      <div className={styles.right}>
        <span className={`${styles.roleBadge} ${user.role === 'instructor' ? styles.roleInstructor : styles.roleTA}`}>
          {user.role === 'instructor' ? 'Instructor' : 'TA'}
        </span>
        <span className={styles.userEmail}>{user.email}</span>
        <button className={styles.logoutBtn} onClick={logout}>
          <i className="ti ti-logout" />
        </button>
      </div>
    </nav>
  );
}
