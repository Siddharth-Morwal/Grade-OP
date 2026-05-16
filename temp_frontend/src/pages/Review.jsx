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
  const pending = submissions.filter(s => s.status === 'pending').length;
  const approved = submissions.filter(s => s.status === 'approved').length;
  const overridden = submissions.filter(s => s.status === 'overridden').length;

  const doApprove = useCallback(() => {
    if (!selected || selected.status !== 'pending') return;
    approveSubmission(selected.id);
    if (selectedIdx < submissions.length - 1) setSelectedIdx(i => i + 1);
    setOverrideOpen(false);
  }, [selected, selectedIdx, submissions.length, approveSubmission]);

  const doOverride = useCallback(() => {
    if (!selected || selected.status !== 'pending') return;
    setOverrideOpen(o => !o);
    setOverrideScore(String(selected.score));
    setOverrideReason('');
  }, [selected]);

  function confirmOverride() {
    const score = parseInt(overrideScore);
    if (isNaN(score) || score < 0 || score > selected.max) return;
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
        <StatCard label="Flagged"       value={submissions.filter(s=>s.plagiarism).length} color="amber" />
      </div>

      <div className={styles.layout}>
        {/* LEFT: list */}
        <div className={styles.list}>
          {submissions.map((s, i) => (
            <div
              key={s.id}
              className={`${styles.listItem} ${i === selectedIdx ? styles.listItemActive : ''}`}
              onClick={() => setSelectedIdx(i)}
            >
              <div className={styles.listName}>
                {s.name}
                {s.plagiarism && <i className="ti ti-alert-triangle" style={{ color: 'var(--amber)', fontSize: 12, marginLeft: 5 }} />}
              </div>
              <div className={styles.listMeta}>
                <span>{s.roll}</span>
                <span style={{ color: s.status === 'approved' ? 'var(--accent)' : s.status === 'overridden' ? 'var(--red)' : 'var(--amber)' }}>
                  {s.status}
                </span>
              </div>
              <div className={styles.listScore} style={{ color: scoreColor(s.pct) }}>
                {s.score}/{s.max}
              </div>
            </div>
          ))}
        </div>

        {/* RIGHT: detail panel */}
        <div className={styles.panel}>
          {!selected ? <EmptyState message="Select a submission to review" /> : (
            <>
              {selected.plagiarism && (
                <div className={styles.plagBanner}>
                  <i className="ti ti-alert-triangle" />
                  <span><strong>Plagiarism Flag:</strong> High structural similarity detected. Manual review required before approval.</span>
                </div>
              )}

              <div className={styles.panelHeader}>
                <div>
                  <div className={styles.studentName}>{selected.name}</div>
                  <div className={styles.studentMeta}>
                    {selected.roll} &nbsp;·&nbsp; {selected.score}/{selected.max} &nbsp;·&nbsp;
                    <span style={{ color: scoreColor(selected.pct) }}>{selected.pct}%</span>
                  </div>
                </div>
                <div className={styles.panelActions}>
                  {selected.status === 'pending' ? (
                    <>
                      <Btn variant="approve" icon="check" onClick={doApprove}>
                        Approve <Kbd>A</Kbd>
                      </Btn>
                      <Btn variant="danger" icon="edit" onClick={doOverride}>
                        Override <Kbd>O</Kbd>
                      </Btn>
                    </>
                  ) : (
                    <Pill variant={selected.status === 'approved' ? 'green' : 'red'}>
                      {selected.status.charAt(0).toUpperCase() + selected.status.slice(1)}
                      {selected.overrideReason && ` — ${selected.overrideReason}`}
                    </Pill>
                  )}
                </div>
              </div>

              {overrideOpen && (
                <div className={styles.overrideBox}>
                  <div className={styles.overrideTitle}>Override Score</div>
                  <div className={styles.overrideRow}>
                    <div>
                      <div className={styles.miniLabel}>New Score (max {selected.max})</div>
                      <input
                        className={styles.overrideInput}
                        type="number" min="0" max={selected.max}
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
                  <span>Scanned answer sheet — {selected.roll}_script.pdf</span>
                  <span style={{ fontSize: 11, opacity: 0.45 }}>Page 1 of 3 · Click to zoom</span>
                </div>
              </div>

              {/* Breakdown */}
              <div>
                <div className={styles.sectionLabel}>Per-Question Breakdown</div>
                <div className={styles.breakdown}>
                  {selected.breakdown.map((b, i) => {
                    const pct = Math.round(b.score / b.max * 100);
                    const fill = pct === 0 ? 'var(--red)' : pct < 70 ? 'var(--amber)' : 'var(--accent)';
                    return (
                      <div key={i} className={styles.bRow}>
                        <div className={styles.bQ}>{b.q}</div>
                        <div className={styles.bTopic}>{b.topic}</div>
                        <div className={styles.bBarWrap}>
                          <div className={styles.bBar} style={{ width: `${Math.min(pct, 100)}%`, background: fill }} />
                        </div>
                        <div className={styles.bFeedback}>{b.feedback}</div>
                        <div className={styles.bScore} style={{ color: fill }}>{b.score}/{b.max}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* AI Justification */}
              <div className={styles.justification}>
                <span className={styles.aiTag}>AI Justification</span>
                {selected.justification}
              </div>
            </>
          )}
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
