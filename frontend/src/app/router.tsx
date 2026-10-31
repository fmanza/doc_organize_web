import { createBrowserRouter, type RouteObject } from 'react-router';

import { HomePage } from '../features/health/HomePage';
import { Layout } from './Layout';
import { NotFoundPage } from './NotFoundPage';

// Las rutas de cada fase (ubicaciones, proyectos, ejecuciones…) se añaden como hijas de Layout.
export const routes: RouteObject[] = [
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
