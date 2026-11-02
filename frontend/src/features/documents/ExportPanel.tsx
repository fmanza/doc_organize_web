import { Button, Card, Group, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { type RunRequest, useEnqueueRun } from '../projects/useProjects';

const ZIP_SIZE: RunRequest = { operation: 'export_zip', dry_run: true };
const ZIP: RunRequest = { operation: 'export_zip', dry_run: false };
const CACHE_XLSX: RunRequest = { operation: 'export_xlsx', kind: 'cache' };
const ERRORS_XLSX: RunRequest = { operation: 'export_xlsx', kind: 'errors' };

/**
 * Exportaciones del proyecto (sustituye a las descargas de la web integrada): cada una es una ejecución y el fichero
 * queda en su detalle para descargarlo. El ZIP puede ser enorme, así que primero se puede calcular su tamaño.
 * Cualquier miembro puede exportar.
 */
export function ExportPanel({ projectId }: { projectId: number }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const enqueue = useEnqueueRun(projectId);
  const launch = (body: RunRequest) =>
    enqueue.mutate(body, { onSuccess: (run) => void navigate(`/runs/${run.id}`) });
  /** Solo gira el botón pulsado; los demás se desactivan mientras se encola. */
  const state = (body: RunRequest) => {
    const pressed = enqueue.isPending && JSON.stringify(enqueue.variables) === JSON.stringify(body);
    return { loading: pressed, disabled: enqueue.isPending && !pressed };
  };

  return (
    <Card withBorder>
      <Title order={3} size="h4" mb="xs">
        {t('documents.export.title')}
      </Title>
      <Text size="sm" c="dimmed" mb="sm">
        {t('documents.export.intro')}
      </Text>
      <Group>
        <Button variant="default" {...state(ZIP_SIZE)} onClick={() => launch(ZIP_SIZE)}>
          {t('documents.export.zipSize')}
        </Button>
        <Button {...state(ZIP)} onClick={() => launch(ZIP)}>
          {t('documents.export.zip')}
        </Button>
        <Button variant="light" {...state(CACHE_XLSX)} onClick={() => launch(CACHE_XLSX)}>
          {t('documents.export.cacheXlsx')}
        </Button>
        <Button variant="light" {...state(ERRORS_XLSX)} onClick={() => launch(ERRORS_XLSX)}>
          {t('documents.export.errorsXlsx')}
        </Button>
      </Group>
      {enqueue.isError && <ErrorAlert error={enqueue.error} mt="sm" />}
    </Card>
  );
}
