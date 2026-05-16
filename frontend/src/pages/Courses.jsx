import { COURSES } from '../data/mockData';
import { useApp } from '../hooks/useApp';
import { SectionHeader, StatCard, Pill, Btn } from '../components/UI';
import styles from './Courses.module.css';

export default function Courses({ onNav, onSelectCourse }) {
  const { user, submissions } = useApp();
  const pending = submissions.filter(s => s.status === 'pending').length;

  return (
    <div className={styles.page}>
      <SectionHeader title="Courses" sub="Spring 2026">
        {user.role === 'instructor'
          ? <Btn variant="primary" icon="plus" onClick={() => onNav('upload')}>New Exam</Btn>
          : <Btn variant="primary" icon="checkup-list" onClick={() => onNav('review')}>Open Review Queue</Btn>
        }
      </SectionHeader>

      <div className={styles.statsRow}>
        <StatCard label="Total Exams" value="12" color="blue" />
        <StatCard label="Graded" value="9" color="green" />
        <StatCard label="Pending Review" value={pending} color="amber" />
        <StatCard label="Avg Score" value="74%" />
      </div>

      <div className={styles.grid}>
        {COURSES.map(c => (
          <CourseCard key={c.id} course={c} role={user.role} onClick={() => onSelectCourse(c)} />
        ))}
      </div>
    </div>
  );
}

function CourseCard({ course, role, onClick }) {
  return (
    <div className={styles.card} onClick={onClick}>
      <div className={styles.cardAccent} />
      <div className={styles.code}>{course.code}</div>
      <div className={styles.name}>{course.name}</div>
      <div className={styles.meta}>
        <span><i className="ti ti-users" /> {course.students} students</span>
        <span><i className="ti ti-file-text" /> {course.exams} exams</span>
        <span><i className="ti ti-check" /> {course.graded} graded</span>
      </div>
      {course.pending > 0 && (
        <div className={styles.pendingRow}>
          <Pill variant="amber"><i className="ti ti-clock" />{course.pending} pending review</Pill>
        </div>
      )}
      <div className={styles.cardFooter}>
        <span>{role === 'instructor' ? 'Upload exam →' : 'View results →'}</span>
      </div>
    </div>
  );
}
