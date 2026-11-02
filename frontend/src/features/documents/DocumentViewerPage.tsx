import { Alert, Anchor, Center, Code, Group, Loader, Stack, Tabs, Title, Typography } from '@mantine/core';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams, useSearchParams } from 'react-router';

import { ApiError } from '../../api/client';
import { ErrorAlert } from '../../components/ErrorAlert';
import { joinRelative, renderMarkdown } from './renderMarkdown';
import { outputUrl, useOutputText } from './useDocuments';

function OutputError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (error instanceof ApiError && error.problem.status === 404) {
    return <Alert color="gray">{t('documents.viewer.missing')}</Alert>;
  }
  return <ErrorAlert error={error} />;
}

function Loading() {
  const { t } = useTranslation();
  return (
    <Center>
      <Loader aria-label={t('common.loading')} />
    </Center>
  );
}

/**
 * Visor de un documento convertido: su Markdown (saneado, con sus imágenes) y su JSON. Las salidas se piden a la API,
 * que solo sirve ficheros de `Conversión/` del proyecto con tipo fijo.
 */
export function DocumentViewerPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const [params] = useSearchParams();
  const path = params.get('path') ?? '';
  const hasJson = /\.md$/i.test(path);
  const jsonPath = path.replace(/\.md$/i, '.json');
  const [tab, setTab] = useState<string | null>('markdown');
  const markdown = useOutputText(projectId, path || null);
  const json = useOutputText(projectId, tab === 'json' && hasJson ? jsonPath : null);

  const html = useMemo(
    () =>
      markdown.data === undefined
        ? ''
        : renderMarkdown(markdown.data, (relative) => {
            const target = joinRelative(path, relative);
            return target === null ? null : outputUrl(projectId, target);
          }),
    [markdown.data, path, projectId],
  );
  const prettyJson = useMemo(() => {
    if (json.data === undefined) return '';
    try {
      return JSON.stringify(JSON.parse(json.data), null, 2);
    } catch {
      return json.data;
    }
  }, [json.data]);

  const back = (
    <Anchor component={Link} to={`/projects/${projectId}/documents`} size="sm">
      {t('documents.viewer.back')}
    </Anchor>
  );
  if (!path) {
    return (
      <Stack>
        {back}
        <Alert color="gray">{t('documents.viewer.missing')}</Alert>
      </Stack>
    );
  }
  return (
    <Stack>
      {back}
      <Group justify="space-between" align="flex-end">
        <Title order={2} style={{ wordBreak: 'break-all' }}>
          {path.split('/').at(-1) ?? path}
        </Title>
        <Group gap="md">
          <Anchor href={outputUrl(projectId, path)} download size="sm">
            {t('documents.viewer.downloadMarkdown')}
          </Anchor>
          {hasJson && (
            <Anchor href={outputUrl(projectId, jsonPath)} download size="sm">
              {t('documents.viewer.downloadJson')}
            </Anchor>
          )}
        </Group>
      </Group>
      <Tabs value={tab} onChange={setTab}>
        <Tabs.List>
          <Tabs.Tab value="markdown">{t('documents.viewer.markdown')}</Tabs.Tab>
          {hasJson && <Tabs.Tab value="json">{t('documents.viewer.json')}</Tabs.Tab>}
        </Tabs.List>
        <Tabs.Panel value="markdown" pt="md">
          {markdown.isPending ? (
            <Loading />
          ) : markdown.isError ? (
            <OutputError error={markdown.error} />
          ) : (
            <Typography>
              {/* HTML ya saneado por DOMPurify en renderMarkdown */}
              <div style={{ overflowWrap: 'anywhere' }} dangerouslySetInnerHTML={{ __html: html }} />
            </Typography>
          )}
        </Tabs.Panel>
        <Tabs.Panel value="json" pt="md">
          {json.isPending ? (
            <Loading />
          ) : json.isError ? (
            <OutputError error={json.error} />
          ) : (
            <Code block style={{ maxHeight: '70vh', overflow: 'auto' }}>
              {prettyJson}
            </Code>
          )}
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
