import { Navigate, Route, Routes } from 'react-router-dom';

import { ROUTES } from './app/routes';
import AppLayout from './components/AppLayout';
import LoginPage from './pages/LoginPage';
import NotFoundPage from './pages/NotFoundPage';
import RecipePage from './pages/RecipePage';

/**
 * Routing table of the application, nothing else.
 *
 * `/` is not a page yet, so it redirects to the login screen (`replace`, so "back" does
 * not bounce between the two). Every other address is rendered inside `AppLayout`, which
 * keeps the navigation on screen, and the last route turns an unknown address into a 404
 * page instead of a blank window.
 */
export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path={ROUTES.login} element={<LoginPage />} />
        <Route path={ROUTES.recipe} element={<RecipePage />} />
        <Route path={ROUTES.notFound} element={<NotFoundPage />} />
      </Route>
      <Route path={ROUTES.home} element={<Navigate to={ROUTES.login} replace />} />
    </Routes>
  );
}
