import styles from './UI.module.css';

export function Pill({ children, variant = 'gray' }) {
  return <span className={`${styles.pill} ${styles['pill_' + variant]}`}>{children}</span>;
}

export function Kbd({ children }) {
  return <kbd className={styles.kbd}>{children}</kbd>;
}

export function StatCard({ label, value, color }) {
  return (
    <div className={styles.statCard}>
      <div className={styles.statLabel}>{label}</div>
      <div className={`${styles.statValue} ${color ? styles['stat_' + color] : ''}`}>{value}</div>
    </div>
  );
}

export function SectionHeader({ title, sub, children }) {
  return (
    <div className={styles.sectionHeader}>
      <div className={styles.sectionTitles}>
        <h2 className={styles.sectionTitle}>{title}</h2>
        {sub && <span className={styles.sectionSub}>// {sub}</span>}
      </div>
      {children && <div className={styles.sectionActions}>{children}</div>}
    </div>
  );
}

export function Btn({ children, variant = 'outline', onClick, disabled, icon, full }) {
  return (
    <button
      className={`${styles.btn} ${styles['btn_' + variant]} ${full ? styles.btnFull : ''}`}
      onClick={onClick}
      disabled={disabled}
    >
      {icon && <i className={`ti ti-${icon}`} />}
      {children}
    </button>
  );
}

export function FormField({ label, children }) {
  return (
    <div className={styles.formField}>
      <label className={styles.fieldLabel}>{label}</label>
      {children}
    </div>
  );
}

export function Input({ ...props }) {
  return <input className={styles.input} {...props} />;
}

export function Textarea({ ...props }) {
  return <textarea className={styles.textarea} {...props} />;
}

export function Select({ children, ...props }) {
  return <select className={styles.select} {...props}>{children}</select>;
}

export function Toast({ msg, type }) {
  if (!msg) return null;
  return (
    <div className={`${styles.toast} ${styles['toast_' + type]}`}>
      <i className={`ti ti-${type === 'success' ? 'check' : type === 'override' ? 'edit' : 'info-circle'}`} />
      {msg}
    </div>
  );
}

export function LoadingBar() {
  return <div className={styles.loadingBar} />;
}

export function EmptyState({ icon = 'hand-click', message }) {
  return (
    <div className={styles.emptyState}>
      <i className={`ti ti-${icon}`} />
      <p>{message}</p>
    </div>
  );
}
