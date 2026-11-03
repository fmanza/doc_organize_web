import { Center, Loader } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { NoPermission } from '../../components/NoPermission';
import { can, type Permission, useMe } from './useAuth';

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

/**
 * Rutas de administración (Fase 9): con `instance`, solo el admin de instancia; con `permission`, quien lo tenga en
 * su tenant activo. Sin acceso se ve el estado «sin permiso» (la API lo exige igualmente).
 */
export function RequireAccess({ permission, instance }: { permission?: Permission; instance?: boolean }) {
  const { data: me } = useMe();
  const allowed = instance ? !!me?.is_instance_admin : permission ? can(me, permission) : !!me;
  return allowed ? <Outlet /> : <NoPermission />;
}
