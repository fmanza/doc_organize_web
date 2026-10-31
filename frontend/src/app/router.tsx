import type { ComponentType } from 'react';
import { createBrowserRouter, type RouteObject } from 'react-router';

import { RequireAdmin, RequireAuth } from '../features/auth/guards';
import { LoginPage } from '../features/auth/LoginPage';
import { HomePage } from '../features/health/HomePage';
import { loadFeatureMessages } from '../i18n';
import { Layout } from './Layout';
import { NotFoundPage } from './NotFoundPage';

/** Ruta lazy: descarga el código de la pantalla y, la primera vez, las traducciones de `features.json`. */
function page(load: () => Promise<ComponentType>): Pick<RouteObject, 'lazy'> {
  return {
    lazy: async () => {
      const [Component] = await Promise.all([load(), loadFeatureMessages()]);
      return { Component };
    },
  };
}

// `/login` queda fuera del layout; el resto exige sesión. Las secciones de cada fase se añaden como hijas de Layout
// con `page()` para dividir el bundle.
export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        path: '/',
        element: <Layout />,
        children: [
          { index: true, element: <HomePage /> },
          {
            path: 'account/password',
            ...page(async () => (await import('../features/auth/ChangePasswordPage')).ChangePasswordPage),
          },
          {
            path: 'account/sessions',
            ...page(async () => (await import('../features/admin/SessionsPage')).SessionsPage),
          },
          {
            path: 'admin',
            element: <RequireAdmin />,
            children: [
              { path: 'users', ...page(async () => (await import('../features/admin/UsersPage')).UsersPage) },
              {
                path: 'sessions',
                ...page(async () => (await import('../features/admin/SessionsPage')).SessionsPage),
              },
              { path: 'audit', ...page(async () => (await import('../features/admin/AuditPage')).AuditPage) },
            ],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
