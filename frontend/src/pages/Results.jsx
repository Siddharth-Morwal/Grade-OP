import { useApp } from '../hooks/useApp';
import { COURSES } from '../data/mockData';
import { SectionHeader, StatCard, Pill, Btn } from '../components/UI';
import styles from './Results.module.css';

function scoreColor(pct) {
  if (pct >= 75) return 'green';
  if (pct >= 50) return 'amber';
  return 'red';
}

function scoreFill(pct) {
  if (pct >= 75) return 'var(--accent)';
  if (pct >= 50) return 'var(--amber)';
  return 'var(--red)';
}

export default function Results({ course, onNav, onOpenReview }) {
  const { submissions, showToast } = useApp();
  const c = course || COURSES[0];
  const avg = Math.round(submissions.reduce((a, s) => a + s.pct, 0) / submissions.length);
  const passing = submissions.filter(s => s.pct >= 50).length;
  const highest = Math.max(...submissions.map(s => s.pct));
  const pending = submissions.filter(s => s.status === 'pending').length;

  return (
    <div className={styles.page}>
      {course && (
        <button className={styles.back} onClick={() => onNav('courses')}>
          <i className="ti ti-arrow-left" /> Back to Courses
        </button>
      )}
      <SectionHeader title={c.name} sub={`${c.code} · ${submissions.length} submissions`}>
        <Btn variant="outline" icon="download" onClick={() => showToast('CSV export ready', 'success')}>Export CSV</Btn>
        <Btn variant="outline" icon="printer" onClick={() => showToast('Print view prepared', 'info')}>Print</Btn>
      </SectionHeader>

      <div className={styles.statsRow}>
        <StatCard label="Submissions" value={submissions.length} color="blue" />
        <StatCard label="Avg Score"   value={`${avg}%`} />
        <StatCard label="Passing"     value={passing} color="green" />
        <StatCard label="Highest"     value={`${highest}%`} color="green" />
        <StatCard label="Pending Review" value={pending} color="amber" />
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Student</th>
              <th>Roll No.</th>
              <th>Score</th>
              <th>Percentage</th>
              <th>Status</th>
              <th>Flags</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {submissions.sort((a,b) => b.pct - a.pct).map(s => (
              <tr key={s.id} onClick={() => onOpenReview(s.id)}>
                <td className={styles.tdName}>{s.name}</td>
                <td className={styles.tdMono}>{s.roll}</td>
                <td>
                  <span className={`${styles.score} ${styles['score_' + scoreColor(s.pct)]}`}>
                    {s.score}/{s.max}
                  </span>
                </td>
                <td>
                  <div className={styles.pctCell}>
                    <span className={styles.pctNum} style={{ color: scoreFill(s.pct) }}>{s.pct}%</span>
                    <div className={styles.bar}>
                      <div className={styles.barFill} style={{ width: `${s.pct}%`, background: scoreFill(s.pct) }} />
                    </div>
                  </div>
                </td>
                <td>
                  {s.status === 'approved' && <Pill variant="green"><i className="ti ti-check" />Approved</Pill>}
                  {s.status === 'overridden' && <Pill variant="red"><i className="ti ti-edit" />Overridden</Pill>}
                  {s.status === 'pending' && <Pill variant="amber"><i className="ti ti-clock" />Pending</Pill>}
                </td>
                <td>
                  {s.plagiarism && <Pill variant="amber"><i className="ti ti-alert-triangle" />Plagiarism</Pill>}
                </td>
                <td className={styles.tdAction}>
                  <i className="ti ti-chevron-right" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
