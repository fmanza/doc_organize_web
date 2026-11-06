import { Alert, Button, Group, Modal, Stack, Text, TextInput } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatCount } from '../../components/format';
import { useAuditPurge } from './useAdmin';

/** `AAAA-MM-DD` de hoy en UTC: la purga no admite fechas de fin posteriores (el servidor lo vuelve a comprobar). */
function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Medianoche UTC de una fecha `AAAA-MM-DD` del input. */
function midnightUtc(day: string): string {
  return `${day}T00:00:00Z`;
}

/**
 * Borrar la auditoría del tenant activo entre dos fechas (web 1.2.0, solo el admin de instancia): primero «Comprobar»
 * cuenta las entradas; después hay que teclear ese número para borrar. Cambiar una fecha obliga a comprobar otra vez.
 */
export function AuditPurgeModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const purge = useAuditPurge();
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');
  const [matched, setMatched] = useState<number | null>(null);
  const [typed, setTyped] = useState('');
  const [deleted, setDeleted] = useState<number | null>(null);
  const today = todayUtc();
  const validRange = since !== '' && until !== '' && since < until && until <= today;

  const changeDates = (next: () => void) => {
    next();
    setMatched(null);
    setTyped('');
    purge.reset();
  };
  const range = () => ({ since: midnightUtc(since), until: midnightUtc(until) });
  const check = () =>
    purge.mutate({ ...range(), dry_run: true }, { onSuccess: (result) => setMatched(result.matched) });
  const remove = () =>
    purge.mutate(
      { ...range(), dry_run: false, confirm_count: matched },
      {
        onSuccess: (result) => setDeleted(result.deleted),
        onError: () => setTyped(''),
      },
    );

  return (
    <Modal opened onClose={onClose} title={t('admin.audit.purge.title')} size="lg">
      {deleted !== null ? (
        <Stack>
          <Alert color="green">
            {t('admin.audit.purge.done', { count: deleted, formatted: formatCount(deleted) })}
          </Alert>
          <Group justify="flex-end">
            <Button onClick={onClose}>{t('common.close')}</Button>
          </Group>
        </Stack>
      ) : (
        <Stack>
          <Text size="sm">{t('admin.audit.purge.intro')}</Text>
          <Group grow align="flex-start">
            <TextInput
              type="date"
              label={t('admin.audit.purge.since')}
              value={since}
              max={today}
              onChange={(event) => {
                const value = event.currentTarget.value;
                changeDates(() => setSince(value));
              }}
            />
            <TextInput
              type="date"
              label={t('admin.audit.purge.until')}
              description={t('admin.audit.purge.untilHint')}
              value={until}
              max={today}
              onChange={(event) => {
                const value = event.currentTarget.value;
                changeDates(() => setUntil(value));
              }}
            />
          </Group>
          {since !== '' && until !== '' && !validRange && (
            <Text size="sm" c="red">
              {t('admin.audit.purge.invalidRange')}
            </Text>
          )}
          {purge.isError && <ErrorAlert error={purge.error} />}
          {matched === null ? (
            <Group justify="flex-end">
              <Button variant="default" onClick={onClose}>
                {t('common.cancel')}
              </Button>
              <Button disabled={!validRange} loading={purge.isPending} onClick={check}>
                {t('admin.audit.purge.check')}
              </Button>
            </Group>
          ) : matched === 0 ? (
            <>
              <Alert color="gray">{t('admin.audit.purge.nothing')}</Alert>
              <Group justify="flex-end">
                <Button onClick={onClose}>{t('common.close')}</Button>
              </Group>
            </>
          ) : (
            <>
              <Alert color="red" title={t('admin.audit.purge.warningTitle')}>
                {t('admin.audit.purge.warning', { count: matched, formatted: formatCount(matched) })}
              </Alert>
              <TextInput
                label={t('admin.audit.purge.confirm', { count: matched })}
                value={typed}
                onChange={(event) => setTyped(event.currentTarget.value)}
                inputMode="numeric"
                autoComplete="off"
              />
              <Group justify="flex-end">
                <Button variant="default" onClick={onClose}>
                  {t('common.cancel')}
                </Button>
                <Button
                  color="red"
                  disabled={typed.trim() !== String(matched)}
                  loading={purge.isPending}
                  onClick={remove}
                >
                  {t('admin.audit.purge.delete', { count: matched })}
                </Button>
              </Group>
            </>
          )}
        </Stack>
      )}
    </Modal>
  );
}
