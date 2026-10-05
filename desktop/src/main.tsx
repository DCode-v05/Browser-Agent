import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import './index.css';

// The app follows the system's light or dark setting, like the viewer inside it.
const dark = window.matchMedia('(prefers-color-scheme: dark)');
const follow = () => document.documentElement.classList.toggle('dark', dark.matches);
dark.addEventListener('change', follow);
follow();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
