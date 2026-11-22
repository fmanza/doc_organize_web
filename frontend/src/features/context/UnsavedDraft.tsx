import { Button, Group, Modal, Stack, Text } from '@mantine/core';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useBlocker } from 'react-router';

/**
 * Aviso al salir de la página del contexto con cambios sin guardar en el manifiesto o el perfil (A3, 2026-11-22).
 * Cambiar de paso (`?paso=`) no avisa: los pasos siguen montados y no se pierde nada. Cerrar la pestaña o recargar lo
 * avisa el navegador (`beforeunload`).
 */
export function UnsavedDraftGuard({ dirty }: { dirty: boolean }) {
  const { t } = useTranslation();
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) => dirty && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (!dirty) {
      return;
    }
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  return (
    <Modal
      opened={blocker.state === 'blocked'}
      onClose={() => blocker.reset?.()}
      title={t('context.unsaved.title')}
    >
      <Stack>
        <Text>{t('context.unsaved.body')}</Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={() => blocker.reset?.()}>
            {t('context.unsaved.stay')}
          </Button>
          <Button color="red" onClick={() => blocker.proceed?.()}>
            {t('context.unsaved.leave')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
