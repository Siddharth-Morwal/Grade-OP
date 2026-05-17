import { useState, useEffect } from 'react';
import { useApp } from '../hooks/useApp';
import api from '../api/client';
import { SectionHeader, StatCard, Pill, Btn } from '../components/UI';
import styles from './Courses.module.css';

export default function Courses({ onNav, onSelectCourse }) {
  const { user } = useApp();
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/exams')
      .then(res => {
        setExams(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch exams:', err);
        setLoading(false);
      });
  }, []);

  const pending = exams.filter(e => e.status === 'pending').length;

  return (
    <div className={styles.page}>
      <SectionHeader title="Exams" sub="Spring 2026">
        {user?.role === 'instructor'
          ? <Btn variant="primary" icon="plus" onClick={() => onNav('upload')}>New Exam</Btn>
          : <Btn variant="primary" icon="checkup-list" onClick={() => onNav('review')}>Open Review Queue</Btn>
        }
      </SectionHeader>

      <div className={styles.statsRow}>
        <StatCard label="Total Exams" value={exams.length} color="blue" />
        <StatCard label="Processing" value={exams.filter(e => e.status === 'processing').length} color="amber" />
        <StatCard label="Published" value={exams.filter(e => e.status === 'published').length} color="green" />
        <StatCard label="Avg Score" value="--" />
      </div>

      <div className={styles.grid}>
        {loading ? <p>Loading exams...</p> : exams.map(e => (
          <CourseCard key={e.id} exam={e} role={user?.role} onClick={() => onSelectCourse(e)} />
        ))}
      </div>
    </div>
  );
}

function CourseCard({ exam, role, onClick }) {
  return (
    <div className={styles.card} onClick={onClick}>
      <div className={styles.cardAccent} />
      <div className={styles.code}>{exam.subject}</div>
      <div className={styles.name}>{exam.title}</div>
      <div className={styles.meta}>
        <span><i className="ti ti-file-text" /> {exam.total_marks} Marks</span>
        <span><i className="ti ti-check" /> Status: {exam.status}</span>
      </div>
      {exam.status === 'pending' && (
        <div className={styles.pendingRow}>
          <Pill variant="amber"><i className="ti ti-clock" />Pending Processing</Pill>
        </div>
      )}
      <div className={styles.cardFooter}>
        <span>{role === 'instructor' ? 'Manage exam →' : 'View results →'}</span>
      </div>
    </div>
  );
}
