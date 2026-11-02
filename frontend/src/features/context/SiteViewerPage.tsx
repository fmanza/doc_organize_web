import { Alert, Anchor, Button, Center, Group, Loader, Stack, Text, Title } from '@mantine/core';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { useProject } from '../projects/useProjects';
import { useOpenSite } from './useContext';

/** Permisos del iframe: scripts del sitio en un origen opaco (sin `allow-same-origin`), como su CSP (ADR-010). */
export const SITE_SANDBOX = 'allow-scripts allow-popups';

/**
 * Visor del sitio Zensical del contexto: el sitio es contenido no confiable y se carga aislado (iframe `sandbox` y CSP
 * `sandbox` propia en `/site/<token>/`), nunca en el origen de la app.
 */
export function SiteViewerPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const open = useOpenSite(projectId);
  const { mutate } = open;

  useEffect(() => {
    mutate();
  }, [mutate]);

  if (project.isError) {
    return <ErrorAlert error={project.error} />;
  }
  if (project.isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  return (
    <Stack h="calc(100dvh - 120px)">
      <Anchor component={Link} to={`/projects/${projectId}/context`} size="sm">
        {t('context.site.back', { name: project.data.name })}
      </Anchor>
      <Group justify="space-between">
        <Title order={2}>{t('context.site.title')}</Title>
        {open.data && (
          <Group>
            <Text size="xs" c="dimmed">
              {t('context.site.expires', { date: formatDateTime(open.data.expires_at) })}
            </Text>
            <Button variant="default" size="xs" onClick={() => mutate()}>
              {t('context.site.renew')}
            </Button>
            <Button
              component="a"
              href={open.data.url}
              target="_blank"
              rel="noopener noreferrer"
              size="xs"
              variant="light"
            >
              {t('context.site.newTab')}
            </Button>
          </Group>
        )}
      </Group>
      <Alert color="gray">{t('context.site.isolated')}</Alert>
      {open.isError ? (
        <ErrorAlert error={open.error} />
      ) : !open.data ? (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      ) : (
        <iframe
          title={t('context.site.frame')}
          src={open.data.url}
          sandbox={SITE_SANDBOX}
          referrerPolicy="no-referrer"
          style={{ flex: 1, width: '100%', border: '1px solid var(--mantine-color-default-border)' }}
        />
      )}
    </Stack>
  );
}
