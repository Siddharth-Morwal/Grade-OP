import { useState, useEffect, useCallback } from 'react';
import { useApp } from '../hooks/useApp';
import { SectionHeader, StatCard, Pill, Btn, Kbd, EmptyState } from '../components/UI';
import styles from './Review.module.css';

function scoreColor(pct) {
  if (pct >= 75) return 'var(--accent)';
  if (pct >= 50) return 'var(--amber)';
  return 'var(--red)';
}

export default function Review({ initialId }) {
  const { submissions, approveSubmission, overrideSubmission } = useApp();
  const [selectedIdx, setSelectedIdx] = useState(() => {
    if (initialId) return submissions.findIndex(s => s.id === initialId);
    return 0;
  });
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideScore, setOverrideScore] = useState('');
  const [overrideReason, setOverrideReason] = useState('');

  const selected = submissions[selectedIdx];
  const pending = submissions.filter(s => s.review_status === 'pending').length;
  const approved = submissions.filter(s => s.review_status === 'approved').length;
  const overridden = submissions.filter(s => s.review_status === 'overridden').length;

  const doApprove = useCallback(() => {
    if (!selected || selected.review_status !== 'pending') return;
    approveSubmission(selected.id);
    if (selectedIdx < submissions.length - 1) setSelectedIdx(i => i + 1);
    setOverrideOpen(false);
  }, [selected, selectedIdx, submissions.length, approveSubmission]);

  const doOverride = useCallback(() => {
    if (!selected || selected.review_status !== 'pending') return;
    setOverrideOpen(o => !o);
    setOverrideScore(String(selected.score));
    setOverrideReason('');
  }, [selected]);

  function confirmOverride() {
    const score = parseInt(overrideScore);
    if (isNaN(score) || score < 0 || score > selected.max_score) return;
    overrideSubmission(selected.id, score, overrideReason);
    setOverrideOpen(false);
    if (selectedIdx < submissions.length - 1) setSelectedIdx(i => i + 1);
  }

  useEffect(() => {
    function onKey(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'a' || e.key === 'A') doApprove();
      if (e.key === 'o' || e.key === 'O') doOverride();
      if (e.key === 'ArrowDown') setSelectedIdx(i => Math.min(i + 1, submissions.length - 1));
      if (e.key === 'ArrowUp')   setSelectedIdx(i => Math.max(i - 1, 0));
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [doApprove, doOverride, submissions.length]);

  useEffect(() => { setOverrideOpen(false); }, [selectedIdx]);

  return (
    <div className={styles.page}>
      <SectionHeader title="TA Review Queue" sub={`${pending} pending approvals`} />

      <div className={styles.statsRow}>
        <StatCard label="Pending"       value={pending}   color="amber" />
        <StatCard label="Approved"      value={approved}  color="green" />
        <StatCard label="Overridden"    value={overridden} color="red" />
        <StatCard label="Flagged"       value={submissions.filter(s=>s.flagged_for_review).length} color="amber" />
      </div>

      <div className={styles.layout}>
        {/* LEFT: list */}
        <div className={styles.list}>
          {submissions.map((s, i) => {
            const pct = Math.round((s.score / s.max_score) * 100);
            return (
            <div
              key={s.id}
              className={`${styles.listItem} ${i === selectedIdx ? styles.listItemActive : ''}`}
              onClick={() => setSelectedIdx(i)}
            >
              <div className={styles.listName}>
                {s.student_name || 'Anonymous'}
                {s.flagged_for_review && <i className="ti ti-alert-triangle" style={{ color: 'var(--amber)', fontSize: 12, marginLeft: 5 }} />}
              </div>
              <div className={styles.listMeta}>
                <span>{s.student_roll || s.student_id.substring(0,8)}</span>
                <span style={{ color: s.review_status === 'approved' ? 'var(--accent)' : s.review_status === 'overridden' ? 'var(--red)' : 'var(--amber)' }}>
                  {s.review_status}
                </span>
              </div>
              <div className={styles.listScore} style={{ color: scoreColor(pct) }}>
                {s.score}/{s.max_score}
              </div>
            </div>
          )})}
        </div>

        {/* RIGHT: detail panel */}
        <div className={styles.panel}>
          {!selected ? <EmptyState message="Select a submission to review" /> : (() => {
            const pct = Math.round((selected.score / selected.max_score) * 100);
            return (
            <>
              {selected.flagged_for_review && (
                <div className={styles.plagBanner}>
                  <i className="ti ti-alert-triangle" />
                  <span><strong>Review Flag:</strong> This submission was flagged by the ML pipeline for manual review.</span>
                </div>
              )}

              <div className={styles.panelHeader}>
                <div>
                  <div className={styles.studentName}>{selected.student_name || 'Anonymous'}</div>
                  <div className={styles.studentMeta}>
                    {selected.student_roll || selected.student_id.substring(0,8)} &nbsp;·&nbsp; {selected.score}/{selected.max_score} &nbsp;·&nbsp;
                    <span style={{ color: scoreColor(pct) }}>{pct}%</span>
                  </div>
                </div>
                <div className={styles.panelActions}>
                  {selected.review_status === 'pending' ? (
                    <>
                      <Btn variant="approve" icon="check" onClick={doApprove}>
                        Approve <Kbd>A</Kbd>
                      </Btn>
                      <Btn variant="danger" icon="edit" onClick={doOverride}>
                        Override <Kbd>O</Kbd>
                      </Btn>
                    </>
                  ) : (
                    <Pill variant={selected.review_status === 'approved' ? 'green' : 'red'}>
                      {selected.review_status.charAt(0).toUpperCase() + selected.review_status.slice(1)}
                      {selected.override_reason && ` — ${selected.override_reason}`}
                    </Pill>
                  )}
                </div>
              </div>

              {overrideOpen && (
                <div className={styles.overrideBox}>
                  <div className={styles.overrideTitle}>Override Score</div>
                  <div className={styles.overrideRow}>
                    <div>
                      <div className={styles.miniLabel}>New Score (max {selected.max_score})</div>
                      <input
                        className={styles.overrideInput}
                        type="number" min="0" max={selected.max_score}
                        value={overrideScore}
                        onChange={e => setOverrideScore(e.target.value)}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div className={styles.miniLabel}>Reason</div>
                      <input
                        className={styles.overrideReasonInput}
                        type="text" placeholder="Brief justification..."
                        value={overrideReason}
                        onChange={e => setOverrideReason(e.target.value)}
                      />
                    </div>
                    <Btn variant="primary" icon="check" onClick={confirmOverride}>Confirm</Btn>
                  </div>
                </div>
              )}

              {/* Answer script placeholder */}
              <div className={styles.scriptBlock}>
                <div className={styles.miniLabel} style={{ marginBottom: 10 }}>Student Answer Script</div>
                <div className={styles.scriptPlaceholder}>
                  <i className="ti ti-file-text" style={{ fontSize: 32, color: 'var(--border2)' }} />
                  <span>Scanned answer sheet</span>
                </div>
              </div>

              {/* Breakdown */}
              {selected.per_question_breakdown && (
              <div>
                <div className={styles.sectionLabel}>Per-Question Breakdown</div>
                <div className={styles.breakdown}>
                  {selected.per_question_breakdown.map((b, i) => {
                    const bpct = Math.round(b.score / b.max_score * 100);
                    const fill = bpct === 0 ? 'var(--red)' : bpct < 70 ? 'var(--amber)' : 'var(--accent)';
                    return (
                      <div key={i} className={styles.bRow}>
                        <div className={styles.bQ}>{b.question_id || `Q${i+1}`}</div>
                        <div className={styles.bTopic}>{b.topic || ''}</div>
                        <div className={styles.bBarWrap}>
                          <div className={styles.bBar} style={{ width: `${Math.min(bpct, 100)}%`, background: fill }} />
                        </div>
                        <div className={styles.bFeedback}>{b.feedback || ''}</div>
                        <div className={styles.bScore} style={{ color: fill }}>{b.score}/{b.max_score}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
              )}

              {/* AI Justification */}
              {selected.overall_justification && (
              <div className={styles.justification}>
                <span className={styles.aiTag}>AI Justification</span>
                {selected.overall_justification}
              </div>
              )}
            </>
          )})}
        </div>
      </div>

      <div className={styles.shortcutBar}>
        <span><Kbd>A</Kbd> Approve</span>
        <span><Kbd>O</Kbd> Override</span>
        <span><Kbd>↑</Kbd><Kbd>↓</Kbd> Navigate</span>
        <span><Kbd>F</Kbd> Flag</span>
      </div>
    </div>
  );
}
