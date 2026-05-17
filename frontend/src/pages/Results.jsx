import { useState, useEffect } from 'react';
import { useApp } from '../hooks/useApp';
import api from '../api/client';
import { SectionHeader, StatCard, Pill, Btn, FormField, Input } from '../components/UI';
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
  const { submissions, setSubmissions, showToast, user } = useApp();
  const [loading, setLoading] = useState(true);
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualName, setManualName] = useState('');
  const [manualRoll, setManualRoll] = useState('');
  const [manualScore, setManualScore] = useState('');
  
  function fetchSubmissions() {
    setLoading(true);
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
  }

  useEffect(() => {
    fetchSubmissions();
  }, [course, setSubmissions]);

  async function handleAddManual() {
    if (!manualName || !manualRoll || !manualScore) {
      showToast('Please fill all fields', 'info');
      return;
    }
    if (!course) {
      showToast('Please select a course to add manual grades', 'info');
      return;
    }
    
    try {
      setLoading(true);
      await api.post('/grades/manual', {
        student_name: manualName,
        roll_number: manualRoll,
        score: parseInt(manualScore, 10),
        exam_id: course.id
      });
      showToast('Manual result added successfully', 'success');
      setShowManualModal(false);
      setManualName('');
      setManualRoll('');
      setManualScore('');
      fetchSubmissions();
    } catch (err) {
      console.error(err);
      showToast('Failed to add manual result', 'error');
      setLoading(false);
    }
  }

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
      <SectionHeader title={course ? course.title : "All Reviews"} sub={`${course ? course.course_code || course.subject : ''} · ${submissions.length} submissions`}>
        {course && user?.role === 'teacher' && (
          <Btn variant="primary" icon="plus" onClick={() => setShowManualModal(true)}>Add Manual Result</Btn>
        )}
        <Btn variant="outline" icon="download" onClick={() => showToast('CSV export ready', 'success')}>Export CSV</Btn>
        <Btn variant="outline" icon="printer" onClick={() => showToast('Print view prepared', 'info')}>Print</Btn>
      </SectionHeader>

      {showManualModal && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalCard}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text)' }}>Add Manual Result</h3>
              <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }} onClick={() => setShowManualModal(false)}>
                <i className="ti ti-x" style={{ fontSize: '1.2rem' }} />
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <FormField label="Student Name">
                <Input value={manualName} onChange={e => setManualName(e.target.value)} placeholder="e.g. John Doe" />
              </FormField>
              <FormField label="Roll Number">
                <Input value={manualRoll} onChange={e => setManualRoll(e.target.value)} placeholder="e.g. CS21B043" />
              </FormField>
              <FormField label={`Score (Max: ${course?.total_marks})`}>
                <Input type="number" value={manualScore} onChange={e => setManualScore(e.target.value)} placeholder="e.g. 85" />
              </FormField>
              <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                <Btn variant="primary" icon="check" onClick={handleAddManual}>Submit Result</Btn>
                <Btn variant="outline" onClick={() => setShowManualModal(false)}>Cancel</Btn>
              </div>
            </div>
          </div>
        </div>
      )}

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
