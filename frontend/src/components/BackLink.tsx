import { Anchor } from '@mantine/core';
import type { ReactNode } from 'react';
import { Link } from 'react-router';

import { Icon } from './Icon';
import { BackIcon } from './icons';

/** Enlace «volver» de la cabecera de una página: flecha decorativa y el texto, que es el nombre accesible. */
export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Anchor
      component={Link}
      to={to}
      size="sm"
      style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
    >
      <Icon of={BackIcon} />
      {children}
    </Anchor>
  );
}
