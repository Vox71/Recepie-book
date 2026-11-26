import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { ROUTES } from '../app/routes';
import { useAuth } from './AuthContext';

/** Keep the signed-in screens behind `/login`; the intended address is restored there. */
export default function RequireAuth() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.login} replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
