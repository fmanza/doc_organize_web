import { Badge, MantineProvider, createTheme } from '@mantine/core';
import { type QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

import { createQueryClient } from './queryClient';

const theme = createTheme({
  primaryColor: 'blue',
  defaultRadius: 'md',
  components: {
    // La etiqueta de Badge recorta su texto (overflow oculto), así que su ancho mínimo es casi cero: en una celda de
    // tabla junto a un texto largo, el navegador la encogía hasta cortarla o dejarla en blanco. Nunca menos que su texto.
    Badge: Badge.extend({ styles: { root: { minWidth: 'max-content' } } }),
  },
});

interface ProvidersProps {
  children: ReactNode;
  queryClient?: QueryClient;
  /**
   * `test` desactiva las transiciones y los portales de Mantine. En jsdom, con la suite en paralelo, la transición de
   * apertura de un menú a veces no terminaba y el desplegable se quedaba en `display: none`.
   */
  env?: 'default' | 'test';
}

export function Providers({ children, queryClient, env = 'default' }: ProvidersProps) {
  const [client] = useState(() => queryClient ?? createQueryClient());
  return (
    <MantineProvider theme={theme} defaultColorScheme="auto" env={env}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </MantineProvider>
  );
}
