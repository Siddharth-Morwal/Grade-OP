export const COURSES = [
  { id: 'cs301', code: 'CS 301', name: 'Data Structures & Algorithms', exams: 3, students: 42, graded: 2, pending: 5 },
  { id: 'ma201', code: 'MA 201', name: 'Linear Algebra', exams: 2, students: 35, graded: 2, pending: 0 },
  { id: 'cs401', code: 'CS 401', name: 'Operating Systems', exams: 4, students: 38, graded: 3, pending: 2 },
  { id: 'ec101', code: 'EC 101', name: 'Microeconomics', exams: 3, students: 55, graded: 2, pending: 0 },
];

export const EXAMS = [
  { id: 'e1', courseId: 'cs301', title: 'Mid-Semester Examination', date: '2026-03-15', totalMarks: 50, status: 'graded', submissions: 42 },
  { id: 'e2', courseId: 'cs301', title: 'Unit Test 1 — Arrays & Trees', date: '2026-02-08', totalMarks: 25, status: 'graded', submissions: 42 },
  { id: 'e3', courseId: 'cs301', title: 'End-Semester Examination', date: '2026-05-01', totalMarks: 100, status: 'pending', submissions: 0 },
];

export const SUBMISSIONS = [
  {
    id: 1, examId: 'e1', name: 'Aryan Sharma', roll: 'CS21B043', score: 42, max: 50, pct: 84, status: 'pending', plagiarism: false,
    breakdown: [
      { q: 'Q1', topic: 'Time Complexity', score: 10, max: 10, feedback: 'Perfect derivation. Master theorem applied correctly.' },
      { q: 'Q2', topic: 'Binary Search Tree', score: 8, max: 10, feedback: 'Missing edge case for empty array input.' },
      { q: 'Q3', topic: 'Dynamic Programming', score: 7, max: 15, feedback: 'Incorrect recurrence relation setup; subproblems identified correctly though.' },
      { q: 'Q4', topic: 'Graph Traversal', score: 9, max: 10, feedback: 'Good proof, minor notation inconsistencies.' },
      { q: 'Q5', topic: 'Bonus', score: 8, max: 5, feedback: 'Excellent — answered bonus correctly for extra credit.' },
    ],
    justification: 'The student demonstrates solid understanding of algorithmic complexity. Q3 shows a conceptual gap in DP — the recurrence relation was incorrectly set up, leading to a suboptimal solution. Partial credit awarded for correct identification of subproblems. Overall strong performance.',
  },
  {
    id: 2, examId: 'e1', name: 'Priya Nair', roll: 'CS21B017', score: 38, max: 50, pct: 76, status: 'pending', plagiarism: true,
    breakdown: [
      { q: 'Q1', topic: 'Time Complexity', score: 9, max: 10, feedback: 'Minor computational error in the final step.' },
      { q: 'Q2', topic: 'Binary Search Tree', score: 10, max: 10, feedback: 'Fully correct.' },
      { q: 'Q3', topic: 'Dynamic Programming', score: 6, max: 15, feedback: 'Logic structure highly similar to submission CS21B043.' },
      { q: 'Q4', topic: 'Graph Traversal', score: 8, max: 10, feedback: 'Good overall approach.' },
      { q: 'Q5', topic: 'Bonus', score: 5, max: 5, feedback: 'Correct.' },
    ],
    justification: 'Generally strong performance. PLAGIARISM FLAG: Q3 answer shares highly similar logical structure (85% similarity score) with student CS21B043. Recommend manual comparison before approval.',
  },
  {
    id: 3, examId: 'e1', name: 'Rohan Mehta', roll: 'CS21B029', score: 31, max: 50, pct: 62, status: 'pending', plagiarism: false,
    breakdown: [
      { q: 'Q1', topic: 'Time Complexity', score: 8, max: 10, feedback: 'Correct approach, arithmetic error in last step.' },
      { q: 'Q2', topic: 'Binary Search Tree', score: 5, max: 10, feedback: 'Incomplete — only partial solution shown.' },
      { q: 'Q3', topic: 'Dynamic Programming', score: 10, max: 15, feedback: 'Good understanding, missing formal proof.' },
      { q: 'Q4', topic: 'Graph Traversal', score: 5, max: 10, feedback: 'Confused BFS and DFS implementation.' },
      { q: 'Q5', topic: 'Bonus', score: 3, max: 5, feedback: 'Partially correct.' },
    ],
    justification: 'Student shows foundational understanding but struggles with formal proof writing. Q4 reveals a conceptual confusion between graph traversal algorithms. Recommend targeted revision on BFS vs DFS.',
  },
  {
    id: 4, examId: 'e1', name: 'Sneha Iyer', roll: 'CS21B051', score: 47, max: 50, pct: 94, status: 'pending', plagiarism: false,
    breakdown: [
      { q: 'Q1', topic: 'Time Complexity', score: 10, max: 10, feedback: 'Excellent.' },
      { q: 'Q2', topic: 'Binary Search Tree', score: 10, max: 10, feedback: 'Excellent.' },
      { q: 'Q3', topic: 'Dynamic Programming', score: 14, max: 15, feedback: 'Near perfect — minor LaTeX notation inconsistency.' },
      { q: 'Q4', topic: 'Graph Traversal', score: 10, max: 10, feedback: 'Perfect.' },
      { q: 'Q5', topic: 'Bonus', score: 3, max: 5, feedback: 'Partially answered bonus.' },
    ],
    justification: 'Outstanding performance across all sections. Near-perfect on Q3 with a minor notation inconsistency in the final step. Highly recommend approval.',
  },
  {
    id: 5, examId: 'e1', name: 'Vikram Das', roll: 'CS21B008', score: 22, max: 50, pct: 44, status: 'pending', plagiarism: false,
    breakdown: [
      { q: 'Q1', topic: 'Time Complexity', score: 6, max: 10, feedback: 'Setup correct, solution incorrect.' },
      { q: 'Q2', topic: 'Binary Search Tree', score: 4, max: 10, feedback: 'Multiple errors throughout.' },
      { q: 'Q3', topic: 'Dynamic Programming', score: 5, max: 15, feedback: 'Only first step correct.' },
      { q: 'Q4', topic: 'Graph Traversal', score: 5, max: 10, feedback: 'Attempted but fundamentally incorrect.' },
      { q: 'Q5', topic: 'Bonus', score: 2, max: 5, feedback: 'Incorrect approach.' },
    ],
    justification: 'Student appears to have significant gaps in core concepts. Q3 and Q4 indicate difficulty with both dynamic programming and graph algorithms. Recommend academic support outreach.',
  },
  {
    id: 6, examId: 'e1', name: 'Ananya Singh', roll: 'CS21B062', score: 36, max: 50, pct: 72, status: 'pending', plagiarism: false,
    breakdown: [
      { q: 'Q1', topic: 'Time Complexity', score: 9, max: 10, feedback: 'Good.' },
      { q: 'Q2', topic: 'Binary Search Tree', score: 8, max: 10, feedback: 'Minor sign error in final computation.' },
      { q: 'Q3', topic: 'Dynamic Programming', score: 9, max: 15, feedback: 'Partially complete derivation; stopped before final answer.' },
      { q: 'Q4', topic: 'Graph Traversal', score: 7, max: 10, feedback: 'Correct method, multiple computational errors.' },
      { q: 'Q5', topic: 'Bonus', score: 3, max: 5, feedback: 'Partially correct.' },
    ],
    justification: 'Consistent performance. Multiple computational errors suggest carelessness rather than conceptual gaps. Q3 was left incomplete — unclear if time constraint or knowledge issue.',
  },
  {
    id: 7, examId: 'e1', name: 'Kabir Joshi', roll: 'CS21B034', score: 29, max: 50, pct: 58, status: 'pending', plagiarism: true,
    breakdown: [
      { q: 'Q1', topic: 'Time Complexity', score: 7, max: 10, feedback: 'Correct overall.' },
      { q: 'Q2', topic: 'Binary Search Tree', score: 6, max: 10, feedback: 'Partial credit.' },
      { q: 'Q3', topic: 'Dynamic Programming', score: 8, max: 15, feedback: 'Logic structure similar to CS21B017.' },
      { q: 'Q4', topic: 'Graph Traversal', score: 5, max: 10, feedback: 'Incomplete.' },
      { q: 'Q5', topic: 'Bonus', score: 3, max: 5, feedback: 'Attempted.' },
    ],
    justification: 'PLAGIARISM FLAG: Q3 shows structural similarity with two other submissions. Score reflects only portions that appear original. Manual review strongly recommended before any approval.',
  },
];
