import {
  Alert,
  Anchor,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Mark,
  Pagination,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatCount, formatDateTime } from '../../components/format';
import { ClearSection } from '../../components/listing';
import { canDo, useEnqueueRun, useProject } from '../projects/useProjects';
import { ROOT_FOLDER, SEARCH_PAGE_SIZE, snippetParts, useContentSearch } from './useDocuments';

/**
 * Búsqueda de texto completo en el Markdown convertido (mejora opcional de la Fase 5). El índice se pone al día al
 * terminar cada escaneo; un editor puede actualizarlo a mano (proyectos escaneados antes de la 0.6.0).
 */
export function ContentSearchPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const enqueue = useEnqueueRun(projectId);
  const [text, setText] = useState('');
  const [q] = useDebouncedValue(text.trim(), 400);
  const [folder, setFolder] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const search = useContentSearch(projectId, q, folder, page);

  if (project.isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (project.isError) {
    return <ErrorAlert error={project.error} />;
  }
  const data = search.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / SEARCH_PAGE_SIZE)) : 1;

  return (
    <Stack>
      <Anchor component={Link} to={`/projects/${projectId}/documents`} size="sm">
        {t('documents.contentSearch.back')}
      </Anchor>
      <Group justify="space-between" align="flex-end">
        <Title order={2}>{t('documents.contentSearch.title')}</Title>
        {canDo(project.data, 'editor') && (
          <Button
            variant="default"
            loading={enqueue.isPending}
            onClick={() =>
              enqueue.mutate(
                { operation: 'search_index' },
                { onSuccess: (run) => void navigate(`/runs/${run.id}`) },
              )
            }
          >
            {t('documents.contentSearch.reindex')}
          </Button>
        )}
      </Group>
      {enqueue.isError && <ErrorAlert error={enqueue.error} />}
      <Group align="flex-end">
        <TextInput
          label={t('documents.contentSearch.words')}
          description={t('documents.contentSearch.hint')}
          value={text}
          onChange={(event) => {
            setText(event.currentTarget.value);
            setPage(1);
          }}
          maxLength={200}
          rightSectionPointerEvents="auto"
          rightSection={
            <ClearSection
              text={text}
              onClear={() => {
                setText('');
                setPage(1);
              }}
            />
          }
          style={{ flex: 1, minWidth: 200 }}
        />
        <Select
          label={t('documents.folder')}
          placeholder={t('documents.allFolders')}
          clearable
          value={folder}
          onChange={(value) => {
            setFolder(value);
            setPage(1);
          }}
          data={project.data.source_subpaths.map((subpath) => ({
            value: subpath === '' ? ROOT_FOLDER : subpath,
            label: subpath === '' ? t('documents.rootFolder') : subpath,
          }))}
        />
      </Group>
      {search.isError ? (
        <ErrorAlert error={search.error} />
      ) : q === '' ? (
        <Text c="dimmed">{t('documents.contentSearch.prompt')}</Text>
      ) : !data ? (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      ) : data.indexed_at === null ? (
        <Alert color="gray">{t('documents.contentSearch.noIndex')}</Alert>
      ) : (
        <>
          <Text size="sm" c="dimmed" role="status">
            {t('documents.contentSearch.total', { count: data.total, formatted: formatCount(data.total) })}{' '}
            {t('documents.contentSearch.indexedAt', { date: formatDateTime(data.indexed_at) })}
          </Text>
          {data.items.map((hit) => (
            <Card withBorder key={hit.output_path} padding="sm">
              <Anchor
                component={Link}
                to={`/projects/${projectId}/documents/view?path=${encodeURIComponent(hit.output_path)}`}
                fw={600}
              >
                {hit.title}
              </Anchor>
              <Text size="xs" c="dimmed" ff="monospace" style={{ wordBreak: 'break-all' }}>
                {hit.output_path}
              </Text>
              <Text size="sm" mt={4}>
                {snippetParts(hit.snippet).map((part, index) =>
                  part.match ? <Mark key={index}>{part.text}</Mark> : <span key={index}>{part.text}</span>,
                )}
              </Text>
            </Card>
          ))}
          {pages > 1 && <Pagination total={pages} value={page} onChange={setPage} />}
        </>
      )}
    </Stack>
  );
}
