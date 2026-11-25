import { Button, Group, Modal, Stack, Text, Textarea } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { type User, useUpdateUser } from './useAdmin';

/** Longitud máxima del motivo (la misma que valida la API). */
const REASON_MAX = 200;

/**
 * Bloquear (desactivar) o desbloquear (reactivar) a un usuario (2.7, D1: bloquear es desactivar). El motivo es
 * opcional y solo va a la auditoría. Bloquear cierra sus sesiones.
 */
export function UserBlockModal({ user, onClose }: { user: User; onClose: () => void }) {
  const { t } = useTranslation();
  const update = useUpdateUser();
  const [reason, setReason] = useState('');
  const blocking = user.is_active;
  const action = blocking ? 'block' : 'unblock';

  const confirm = () => {
    const trimmed = reason.trim();
    update.mutate(
      { id: user.id, body: { unlock: false, is_active: !blocking, ...(trimmed ? { reason: trimmed } : {}) } },
      { onSuccess: onClose },
    );
  };

  return (
    <Modal opened onClose={onClose} title={t(`admin.users.${action}.title`, { username: user.username })}>
      <Stack>
        <Text size="sm">{t(`admin.users.${action}.body`)}</Text>
        <Textarea
          label={t('admin.users.block.reason')}
          description={t('admin.users.block.reasonHint')}
          value={reason}
          onChange={(event) => setReason(event.currentTarget.value)}
          maxLength={REASON_MAX}
          rows={2}
        />
        {update.isError && <ErrorAlert error={update.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button color={blocking ? 'orange' : 'blue'} loading={update.isPending} onClick={confirm}>
            {t(`admin.users.${action}.confirm`)}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
