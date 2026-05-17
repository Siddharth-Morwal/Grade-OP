import { useState, useEffect } from 'react';
import { useApp } from '../hooks/useApp';
import api from '../api/client';
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
  const { submissions, setSubmissions, showToast } = useApp();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch reviews for the selected exam (course)
    const url = course ? `/reviews?exam_id=${course.id}` : '/reviews';
    api.get(url)
      .then(res => {
        setSubmissions(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch reviews:', err);
        setLoading(false);
      });
  }, [course, setSubmissions]);

  const avg = submissions.length > 0 ? Math.round(submissions.reduce((a, s) => a + (s.score / s.max_score * 100), 0) / submissions.length) : 0;
  const passing = submissions.filter(s => (s.score / s.max_score) >= 0.5).length;
  const highest = submissions.length > 0 ? Math.max(...submissions.map(s => Math.round((s.score / s.max_score) * 100))) : 0;
  const pending = submissions.filter(s => s.review_status === 'pending').length;

  return (
    <div className={styles.page}>
      {course && (
        <button className={styles.back} onClick={() => onNav('courses')}>
          <i className="ti ti-arrow-left" /> Back to Exams
        </button>
      )}
      <SectionHeader title={course ? course.title : "All Reviews"} sub={`${course ? course.subject : ''} · ${submissions.length} submissions`}>
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
        {loading ? <p style={{padding: '2rem'}}>Loading submissions...</p> : (
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
            {submissions.map(s => {
              const pct = Math.round((s.score / s.max_score) * 100);
              return (
              <tr key={s.id} onClick={() => onOpenReview(s.id)}>
                <td className={styles.tdName}>{s.student_name || 'Anonymous'}</td>
                <td className={styles.tdMono}>{s.student_roll || s.student_id.substring(0,8)}</td>
                <td>
                  <span className={`${styles.score} ${styles['score_' + scoreColor(pct)]}`}>
                    {s.score}/{s.max_score}
                  </span>
                </td>
                <td>
                  <div className={styles.pctCell}>
                    <span className={styles.pctNum} style={{ color: scoreFill(pct) }}>{pct}%</span>
                    <div className={styles.bar}>
                      <div className={styles.barFill} style={{ width: `${pct}%`, background: scoreFill(pct) }} />
                    </div>
                  </div>
                </td>
                <td>
                  {s.review_status === 'approved' && <Pill variant="green"><i className="ti ti-check" />Approved</Pill>}
                  {s.review_status === 'overridden' && <Pill variant="red"><i className="ti ti-edit" />Overridden</Pill>}
                  {s.review_status === 'pending' && <Pill variant="amber"><i className="ti ti-clock" />Pending</Pill>}
                </td>
                <td>
                  {s.flagged_for_review && <Pill variant="amber"><i className="ti ti-alert-triangle" />Flagged</Pill>}
                </td>
                <td className={styles.tdAction}>
                  <i className="ti ti-chevron-right" />
                </td>
              </tr>
            )})}
          </tbody>
        </table>
        )}
      </div>
    </div>
  );
}
