import { Button, Group, Modal, Stack, Text } from '@mantine/core';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from './ErrorAlert';

interface ConfirmModalProps {
  opened: boolean;
  onClose: () => void;
  title: ReactNode;
  /** Texto principal (en un `Text`; `null`/`undefined` no pinta nada); lo demás va en `children`, debajo. */
  message?: ReactNode;
  children?: ReactNode;
  /**
   * Error de la mutación (`mutation.error`); `null`/`undefined` no muestra nada. Quien lo pase debe llamar a
   * `mutation.reset()` al abrir y al cerrar, para no enseñar el error de un intento anterior.
   */
  error?: unknown;
  confirmLabel: ReactNode;
  onConfirm: () => void;
  /** Por omisión, `common.cancel`. */
  cancelLabel?: ReactNode;
  /** Acción destructiva: botón de confirmar en rojo (por omisión); `false`, el color del tema. */
  danger?: boolean;
  loading?: boolean;
  disabled?: boolean;
}

/** Modal de confirmación: texto, error opcional de la API y botones Cancelar / confirmar. */
export function ConfirmModal({
  opened,
  onClose,
  title,
  message,
  children,
  error,
  confirmLabel,
  onConfirm,
  cancelLabel,
  danger = true,
  loading = false,
  disabled = false,
}: ConfirmModalProps) {
  const { t } = useTranslation();
  return (
    <Modal opened={opened} onClose={onClose} title={title}>
      <Stack>
        {message != null && <Text>{message}</Text>}
        {children}
        {error != null && <ErrorAlert error={error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {cancelLabel ?? t('common.cancel')}
          </Button>
          <Button
            {...(danger ? { color: 'red' } : {})}
            loading={loading}
            disabled={disabled}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
