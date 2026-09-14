import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

function App() {
  const [apiStatus, setApiStatus] = useState('Checking connection…');

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/v1/health/', { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('API unavailable');
        const data: unknown = await response.json();
        if (typeof data !== 'object' || data === null || !('status' in data) || data.status !== 'ok') {
          throw new Error('Unexpected health response');
        }
        setApiStatus('API connected');
      })
      .catch(() => {
        if (!controller.signal.aborted) setApiStatus('API offline — start the backend to connect.');
      });
    return () => controller.abort();
  }, []);

  return (
    <main>
      <header><a className="wordmark" href="/">PARALLEL<span> / </span></a><span>Development foundation</span></header>
      <section className="hero" aria-labelledby="title">
        <p className="eyebrow">ONE WORLD. A SHARED HISTORY.</p>
        <h1 id="title">Another world<br />is happening.</h1>
        <p className="intro">Discover information. Decide who to trust. Change what happens next.</p>
        <div className="world"><span className="orb" aria-hidden="true" /><div><p className="eyebrow">FLAGSHIP WORLD</p><h2>Earth-2097</h2><p>A mysterious city has appeared in the Atlantic. Its future belongs to the people who enter this world.</p></div></div>
      </section>
      <section className="foundation" aria-labelledby="foundation-title">
        <h2 id="foundation-title">The foundation is taking shape.</h2>
        <p>This starter connects the web app and API. Accounts, private intel, player actions, and world simulation are scheduled in the project backlog.</p>
        <p className="status" role="status">{apiStatus}</p>
      </section>
      <footer>A fictional universe. Real people. Lasting consequences.</footer>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
