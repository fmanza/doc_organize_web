import { RouterProvider } from 'react-router';

import { Providers } from './Providers';
import { router } from './router';

export function App() {
  return (
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  );
}
