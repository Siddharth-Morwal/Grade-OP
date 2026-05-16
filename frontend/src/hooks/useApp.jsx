import { createContext, useContext, useState } from 'react';
import { SUBMISSIONS } from '../data/mockData';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  const [submissions, setSubmissions] = useState(SUBMISSIONS);
  const [toast, setToast] = useState(null);

  function login(role) {
    setUser({ role, email: role === 'instructor' ? 'instructor@gradeops.io' : 'ta@gradeops.io' });
  }

  function logout() { setUser(null); }

  function approveSubmission(id) {
    setSubmissions(prev => prev.map(s => s.id === id ? { ...s, status: 'approved' } : s));
    showToast('Approved successfully', 'success');
  }

  function overrideSubmission(id, newScore, reason) {
    setSubmissions(prev => prev.map(s => {
      if (s.id !== id) return s;
      return { ...s, score: newScore, pct: Math.round(newScore / s.max * 100), status: 'overridden', overrideReason: reason };
    }));
    showToast('Score overridden', 'override');
  }

  function showToast(msg, type = 'success') {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }

  return (
    <AppContext.Provider value={{ user, login, logout, submissions, approveSubmission, overrideSubmission, toast, showToast }}>
      {children}
    </AppContext.Provider>
  );
}

export const useApp = () => useContext(AppContext);
