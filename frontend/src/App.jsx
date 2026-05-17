import { useState } from 'react';
import { AppProvider, useApp } from './hooks/useApp';
import Navbar from './components/Navbar';
import { Toast } from './components/UI';
import Login from './pages/Login';
import Courses from './pages/Courses';
import Upload from './pages/Upload';
import Results from './pages/Results';
import Review from './pages/Review';

function AppInner() {
  const { user, toast } = useApp();
  const [screen, setScreen] = useState('courses');
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [reviewOpenId, setReviewOpenId] = useState(null);

  if (!user) return <Login />;

  function handleNav(s) {
    setScreen(s);
    if (s !== 'review') setReviewOpenId(null);
  }

  function handleSelectCourse(course) {
    setSelectedCourse(course);
    if (user.role === 'teacher') {
      setScreen('upload');
    } else {
      setScreen('results');
    }
  }

  function handleOpenReview(id) {
    setReviewOpenId(id);
    setScreen('review');
  }

  return (
    <>
      <Navbar screen={screen} onNav={handleNav} />
      {screen === 'courses' && (
        <Courses onNav={handleNav} onSelectCourse={handleSelectCourse} />
      )}
      {screen === 'upload' && (
        <Upload course={selectedCourse} onNav={handleNav} />
      )}
      {screen === 'results' && (
        <Results course={selectedCourse} onNav={handleNav} onOpenReview={handleOpenReview} />
      )}
      {screen === 'review' && (
        <Review initialId={reviewOpenId} key={reviewOpenId} />
      )}
      {toast && <Toast msg={toast.msg} type={toast.type} />}
    </>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppInner />
    </AppProvider>
  );
}
