import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App';

/**
 * Entry point: the router is created once here, so `App` stays a pure component and the
 * tests can wrap it in a `MemoryRouter` with the address they need.
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
