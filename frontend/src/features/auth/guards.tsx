import { Center, Loader } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { NoPermission } from '../../components/NoPermission';
import { useMe } from './useAuth';

/** Rutas con sesión: sin ella redirige a `/login?next=<ruta actual>`. */
export function RequireAuth() {
  const { t } = useTranslation();
  const location = useLocation();
  const { data: me, isPending, error } = useMe();

  if (isPending) {
    return (
      <Center h="100vh">
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (error) {
    return <ErrorAlert error={error} m="md" />;
  }
  if (!me) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return <Outlet />;
}

/** Rutas de administración: un usuario sin rol `admin` ve el estado «sin permiso». */
export function RequireAdmin() {
  const { data: me } = useMe();
  return me?.role === 'admin' ? <Outlet /> : <NoPermission />;
}
