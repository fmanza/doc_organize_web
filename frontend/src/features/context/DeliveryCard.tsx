import { Alert, Button, Card, Checkbox, Group, NumberInput, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { useMe } from '../auth/useAuth';
import { type RunRequest, useEnqueueRun } from '../projects/useProjects';
import { CONTEXT_XLSX } from './useContext';

/**
 * Entregar el contexto (W8): Excel del contexto, sitio sin conexión (ZIP con su SHA-256) y paquete para IA. Cada uno
 * es una ejecución; el fichero, su huella y el aviso quedan en su detalle. Cualquier miembro, como las exportaciones.
 */
export function DeliveryCard({ projectId }: { projectId: number }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const me = useMe();
  const enqueue = useEnqueueRun(projectId);
  const [llmsTxt, setLlmsTxt] = useState(false);
  const [includeText, setIncludeText] = useState(true);
  const [currentOnly, setCurrentOnly] = useState(true);
  const [fullText, setFullText] = useState(false);
  const [maxFileChars, setMaxFileChars] = useState<number | string>('');
  const [redact, setRedact] = useState(true);
  const admin = Boolean(me.data?.is_instance_admin);
  const launch = (body: RunRequest) =>
    enqueue.mutate(body, { onSuccess: (run) => void navigate(`/runs/${run.id}`) });
  const pressed = (operation: string) => enqueue.isPending && enqueue.variables?.operation === operation;

  return (
    <Card withBorder component="section" aria-label={t('context.delivery.title')}>
      <Title order={3} size="h4" mb="xs">
        {t('context.delivery.title')}
      </Title>
      <Text size="sm" c="dimmed" mb="sm">
        {t('context.delivery.intro')}
      </Text>
      <Stack gap="md">
        <Group>
          <Button variant="light" loading={pressed('export_xlsx')} onClick={() => launch(CONTEXT_XLSX)}>
            {t('context.delivery.xlsx')}
          </Button>
          <Text size="xs" c="dimmed">
            {t('context.delivery.xlsxHelp')}
          </Text>
        </Group>

        <Stack gap="xs">
          <Text fw={500} size="sm">
            {t('context.delivery.siteTitle')}
          </Text>
          <Text size="xs" c="dimmed">
            {t('context.delivery.siteHelp')}
          </Text>
          <Checkbox
            label={t('context.delivery.llmsTxt')}
            checked={llmsTxt}
            onChange={(event) => setLlmsTxt(event.currentTarget.checked)}
          />
          <Group>
            <Button
              loading={pressed('export_site')}
              onClick={() => launch({ operation: 'export_site', llms_txt: llmsTxt })}
            >
              {t('context.delivery.site')}
            </Button>
          </Group>
        </Stack>

        <Stack gap="xs">
          <Text fw={500} size="sm">
            {t('context.delivery.bundleTitle')}
          </Text>
          <Text size="xs" c="dimmed">
            {t('context.delivery.bundleHelp')}
          </Text>
          <Group>
            <Checkbox
              label={t('context.delivery.includeText')}
              checked={includeText}
              onChange={(event) => setIncludeText(event.currentTarget.checked)}
            />
            <Checkbox
              label={t('context.delivery.currentOnly')}
              checked={currentOnly}
              onChange={(event) => setCurrentOnly(event.currentTarget.checked)}
            />
            <Checkbox
              label={t('context.delivery.fullText')}
              checked={fullText}
              disabled={!includeText}
              onChange={(event) => setFullText(event.currentTarget.checked)}
            />
          </Group>
          <NumberInput
            label={t('context.delivery.maxFileChars')}
            description={t('context.delivery.maxFileCharsHelp')}
            min={1000}
            max={10_000_000}
            step={10_000}
            w={260}
            value={maxFileChars}
            disabled={!includeText}
            onChange={setMaxFileChars}
          />
          {admin && (
            <Checkbox
              label={t('context.delivery.redact')}
              description={t('context.delivery.redactHelp')}
              checked={redact}
              onChange={(event) => setRedact(event.currentTarget.checked)}
            />
          )}
          <Alert color="orange">{t('context.delivery.bundleWarning')}</Alert>
          {!redact && <Alert color="red">{t('context.delivery.notRedacted')}</Alert>}
          <Group>
            <Button
              loading={pressed('export_ai_bundle')}
              onClick={() =>
                launch({
                  operation: 'export_ai_bundle',
                  include_text: includeText,
                  current_only: currentOnly,
                  redact,
                  max_file_chars: includeText && Number(maxFileChars) ? Number(maxFileChars) : null,
                  max_full_chars: includeText && fullText ? FULL_TEXT_CHARS : null,
                })
              }
            >
              {t('context.delivery.bundle')}
            </Button>
          </Group>
        </Stack>
      </Stack>
      {enqueue.isError && <ErrorAlert error={enqueue.error} mt="sm" />}
    </Card>
  );
}

/** Tope de `llms-full.txt`: unos 2,5 millones de tokens; más no cabe en ningún modelo. */
const FULL_TEXT_CHARS = 10_000_000;
