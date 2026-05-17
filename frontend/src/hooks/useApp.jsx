import { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/client';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  const [submissions, setSubmissions] = useState([]);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      api.get('/auth/me')
        .then(res => setUser(res.data))
        .catch(() => localStorage.removeItem('token'));
    }
  }, []);

  async function login(email, password) {
    try {
      const res = await api.post('/auth/login', { email, password });
      localStorage.setItem('token', res.data.access_token);
      
      const userRes = await api.get('/auth/me');
      setUser(userRes.data);
      return true;
    } catch (e) {
      showToast('Login failed. Check credentials.', 'error');
      return false;
    }
  }

  function logout() { 
    localStorage.removeItem('token');
    setUser(null); 
  }

  async function approveSubmission(id) {
    try {
      await api.patch(`/reviews/${id}/approve`);
      setSubmissions(prev => prev.map(s => s.id === id ? { ...s, review_status: 'approved' } : s));
      showToast('Approved successfully', 'success');
    } catch (e) {
      showToast('Approval failed', 'error');
    }
  }

  async function overrideSubmission(id, newScore, reason) {
    try {
      await api.patch(`/reviews/${id}/override`, { new_score: newScore, override_reason: reason });
      setSubmissions(prev => prev.map(s => {
        if (s.id !== id) return s;
        return { ...s, score: newScore, review_status: 'overridden', override_reason: reason };
      }));
      showToast('Score overridden', 'override');
    } catch (e) {
      showToast('Override failed', 'error');
    }
  }

  function showToast(msg, type = 'success') {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }

  return (
    <AppContext.Provider value={{ user, login, logout, submissions, setSubmissions, approveSubmission, overrideSubmission, toast, showToast }}>
      {children}
    </AppContext.Provider>
  );
}

export const useApp = () => useContext(AppContext);
