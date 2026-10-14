import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import './index.css';

// The app follows the system's light or dark setting, like the viewer inside it. The window's own
// title bar, drawn by the OS on Windows and Linux, is told so it matches.
const dark = window.matchMedia('(prefers-color-scheme: dark)');
const follow = () => {
  document.documentElement.classList.toggle('dark', dark.matches);
  window.desktop.theme(dark.matches);
};
dark.addEventListener('change', follow);
follow();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
