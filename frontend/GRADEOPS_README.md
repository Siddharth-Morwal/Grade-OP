# GradeOps Frontend

React + Vite frontend for the GradeOps Human-in-the-Loop grading system.

## Quick Start

```bash
npm install
npm run dev       # dev server → http://localhost:5173
npm run build     # production build → dist/
```

## Screens

| Screen | Path | Who |
|--------|------|-----|
| Login | `/` | Everyone |
| Courses | `courses` | Both roles |
| Upload Exam | `upload` | Instructor only |
| Results | `results` | Both roles |
| TA Review Queue | `review` | TA only |

## Connecting to Backend

Edit `src/hooks/useApp.jsx` — replace mock functions with real axios calls:

```js
// Example login
const res = await axios.post('http://localhost:8000/auth/login', { email, password });
localStorage.setItem('token', res.data.access_token);
```

See `frontend_guide.md` for the full API endpoint map.

## Keyboard Shortcuts (Review Queue)

| Key | Action |
|-----|--------|
| `A` | Approve submission |
| `O` | Open override form |
| `↑ ↓` | Navigate submissions |
| `F` | Flag for review |
