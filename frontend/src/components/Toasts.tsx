import { Notification, Portal, Stack } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import type { Toast } from './useToasts';

/** Pila de avisos abajo a la derecha, por encima del contenido; se anuncian a los lectores de pantalla. */
export function ToastStack({ toasts, onClose }: { toasts: Toast[]; onClose: (id: number) => void }) {
  const { t } = useTranslation();
  if (toasts.length === 0) {
    return null;
  }
  return (
    <Portal>
      <Stack
        gap="xs"
        aria-live="polite"
        style={{
          position: 'fixed',
          right: 16,
          bottom: 16,
          zIndex: 1000,
          width: 'min(420px, calc(100vw - 32px))',
        }}
      >
        {toasts.map((toast) => (
          <Notification
            key={toast.id}
            color={toast.color}
            title={toast.title}
            role={toast.color === 'red' ? 'alert' : 'status'}
            withBorder
            onClose={() => onClose(toast.id)}
            closeButtonProps={{ 'aria-label': t('common.close') }}
          >
            {toast.message}
          </Notification>
        ))}
      </Stack>
    </Portal>
  );
}
