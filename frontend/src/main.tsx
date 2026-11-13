import '@fontsource-variable/inter/wght.css';
import '@fontsource-variable/lora/wght.css';

import './styles/tokens.css';
import './styles/base.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App';

/**
 * Entry point: fonts and global styles first, then the router.
 *
 * The fonts are the variable builds of `@fontsource`, bundled by Vite and not fetched from
 * a CDN: one woff2 per unicode subset covers every weight the design uses, the app looks
 * the same offline and behind a strict content-security policy, and the browser downloads
 * only the subsets (latin/cyrillic) it actually needs.
 */
const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('index.html has no #root element');
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
