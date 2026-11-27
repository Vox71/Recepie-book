import { Navigate, Route, Routes } from 'react-router-dom';

import { ROUTES } from './app/routes';
import { AuthProvider, useAuth } from './auth/AuthContext';
import RequireAuth from './auth/RequireAuth';
import ErrorBoundary from './components/ErrorBoundary';
import AppLayout from './components/layout/AppLayout';
import AuthLayout from './components/layout/AuthLayout';
import FridgePage from './pages/FridgePage';
import LoginPage from './pages/LoginPage';
import NotFoundPage from './pages/NotFoundPage';
import RecipePage from './pages/RecipePage';

/** `/` has no screen of its own: send a signed-in user to the fridge, a guest to login. */
function HomeRedirect() {
  const { isAuthenticated } = useAuth();
  return <Navigate to={isAuthenticated ? ROUTES.fridge : ROUTES.login} replace />;
}

/**
 * Routing table of the application, nothing else.
 *
 * The login screen has its own frame (header without navigation, design 03), the
 * signed-in screens share another one (pill navigation and the three-column footer,
 * designs 02/04). `/` is not a page yet, so it redirects to the login screen with
 * `replace`; an unknown address is a 404 page inside the signed-in frame.
 */
export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path={ROUTES.login} element={<LoginPage />} />
          </Route>
          <Route element={<RequireAuth />}>
            <Route element={<AppLayout />}>
              <Route path={ROUTES.recipe} element={<RecipePage />} />
              <Route path={ROUTES.fridge} element={<FridgePage />} />
              <Route path={ROUTES.notFound} element={<NotFoundPage />} />
            </Route>
          </Route>
          <Route path={ROUTES.home} element={<HomeRedirect />} />
        </Routes>
      </AuthProvider>
    </ErrorBoundary>
  );
}
