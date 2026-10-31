import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { createMemoryRouter, RouterProvider } from 'react-router';

import { Providers } from '../app/Providers';
import { createQueryClient } from '../app/queryClient';
import { routes } from '../app/router';

/** Renderiza la aplicación completa en `path` con un QueryClient sin reintentos. */
export function renderRoute(path: string) {
  const queryClient = createQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <Providers queryClient={queryClient}>
      <RouterProvider router={router} />
    </Providers>,
  );
}

export function renderWithProviders(ui: ReactElement) {
  return render(<Providers queryClient={createQueryClient()}>{ui}</Providers>);
}
