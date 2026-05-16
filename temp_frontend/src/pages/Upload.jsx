import { useState } from 'react';
import { useApp } from '../hooks/useApp';
import { SectionHeader, Btn, FormField, Input, Textarea, LoadingBar } from '../components/UI';
import styles from './Upload.module.css';

const RUBRIC_PLACEHOLDER = `[
  {
    "question": "Q1",
    "topic": "Time Complexity",
    "max_marks": 10,
    "criteria": "Award full marks for correct Master Theorem application. Deduct 3 marks for missing edge cases."
  },
  {
    "question": "Q2",
    "topic": "Dynamic Programming",
    "max_marks": 15,
    "criteria": "Award 5 marks for correct subproblem identification, 5 for recurrence relation, 5 for final solution."
  }
]`;

export default function Upload({ course, onNav }) {
  const { showToast } = useApp();
  const [files, setFiles] = useState({});
  const [examTitle, setExamTitle] = useState('');
  const [totalMarks, setTotalMarks] = useState('');
  const [rubric, setRubric] = useState('');
  const [loading, setLoading] = useState(false);

  function handleFileDrop(zone, e) {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0] || e.target?.files?.[0];
    if (file) setFiles(prev => ({ ...prev, [zone]: file.name }));
  }

  async function handleSubmit() {
    if (!examTitle) { showToast('Enter an exam title', 'info'); return; }
    setLoading(true);
    await new Promise(r => setTimeout(r, 2200));
    setLoading(false);
    showToast('Pipeline triggered — grading in progress!', 'success');
    onNav('results');
  }

  const zones = [
    { id: 'paper',   icon: 'file-text',   label: 'Question Paper',        hint: 'PDF · PNG · JPG  ·  up to 20 MB' },
    { id: 'key',     icon: 'list-check',   label: 'Answer Key / Rubric',   hint: 'PDF or JSON rubric file' },
    { id: 'scripts', icon: 'files',        label: 'Student Answer Scripts', hint: 'Bulk PDF · multi-select supported' },
  ];

  return (
    <div className={styles.page}>
      <SectionHeader title="Upload Exam" sub={course ? `${course.code} · ${course.name}` : 'New Exam'}>
        <Btn variant="outline" icon="x" onClick={() => onNav('courses')}>Cancel</Btn>
      </SectionHeader>

      {loading && <LoadingBar />}

      <div className={styles.formRow}>
        <FormField label="Exam Title">
          <Input value={examTitle} onChange={e => setExamTitle(e.target.value)} placeholder="e.g. Mid-Semester Examination" />
        </FormField>
        <FormField label="Total Marks">
          <Input type="number" value={totalMarks} onChange={e => setTotalMarks(e.target.value)} placeholder="50" />
        </FormField>
        <FormField label="Course">
          <Input value={course ? `${course.code} — ${course.name}` : ''} readOnly style={{ opacity: 0.6 }} />
        </FormField>
      </div>

      <div className={styles.uploadGrid}>
        {zones.map(z => (
          <UploadZone
            key={z.id}
            icon={z.icon}
            label={z.label}
            hint={z.hint}
            filename={files[z.id]}
            onFile={name => setFiles(prev => ({ ...prev, [z.id]: name }))}
          />
        ))}
        <div className={styles.rubricBox}>
          <div className={styles.rubricLabel}>
            <i className="ti ti-code" />
            JSON Rubric Override
            <span className={styles.optional}>optional</span>
          </div>
          <Textarea
            value={rubric}
            onChange={e => setRubric(e.target.value)}
            placeholder={RUBRIC_PLACEHOLDER}
            style={{ minHeight: 200 }}
          />
        </div>
      </div>

      <div className={styles.pipelineInfo}>
        <i className="ti ti-info-circle" />
        <span>After upload, the ML pipeline will automatically OCR, transcribe, and grade all scripts against your rubric. Results appear within 2–5 minutes.</span>
      </div>

      <div className={styles.actions}>
        <Btn variant="primary" icon="rocket" onClick={handleSubmit} disabled={loading}>
          {loading ? 'Starting Pipeline...' : 'Start Grading Pipeline'}
        </Btn>
        <Btn variant="outline" icon="device-floppy" onClick={() => showToast('Draft saved', 'info')}>Save Draft</Btn>
      </div>
    </div>
  );
}

function UploadZone({ icon, label, hint, filename, onFile }) {
  function handleChange(e) {
    const f = e.target.files?.[0];
    if (f) onFile(f.name);
  }

  return (
    <label className={`${styles.zone} ${filename ? styles.zoneHasFile : ''}`}>
      <input type="file" style={{ display: 'none' }} onChange={handleChange} />
      <i className={`ti ti-${filename ? 'circle-check' : icon} ${styles.zoneIcon}`} />
      <span className={styles.zoneLabel}>{filename ? '✓ ' + label : label}</span>
      <span className={styles.zoneHint}>{filename ? filename : hint}</span>
    </label>
  );
}
