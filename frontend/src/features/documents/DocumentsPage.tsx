import {
  Anchor,
  Badge,
  Box,
  Button,
  Center,
  Group,
  Loader,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatCount, formatDateTime } from '../../components/format';
import { useProject } from '../projects/useProjects';
import { ExportPanel } from './ExportPanel';
import {
  CONVERSION_STATUSES,
  type ConversionStatus,
  type DocumentOut,
  ROOT_FOLDER,
  useDocuments,
} from './useDocuments';

const ROW_HEIGHT = 64;

const STATUS_COLOR: Record<string, string> = { success: 'green', error: 'red' };

function folderLabel(folder: string, root: string): string {
  return folder === '' ? root : folder;
}

/**
 * Documentos del proyecto (caché de doc_organize, sustituye al visor de caché de `dashboard.html.j2`): lista
 * virtualizada y paginada en servidor (100 000 documentos), búsqueda en la ruta, filtro por carpeta, acceso al visor y
 * exportaciones.
 */
export function DocumentsPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const [search, setSearch] = useState('');
  const [debounced] = useDebouncedValue(search.trim(), 300);
  const [folder, setFolder] = useState<string | null>(null);
  const [conversionStatus, setConversionStatus] = useState<ConversionStatus | null>(null);
  const documents = useDocuments(projectId, { search: debounced, folder, conversionStatus });

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
  const root = t('documents.rootFolder');
  const rows = documents.data?.pages.flatMap((page) => page.items) ?? [];
  const total = documents.data?.pages[0]?.total ?? 0;

  return (
    <Stack>
      <Anchor component={Link} to={`/projects/${projectId}`} size="sm">
        {t('documents.backToProject', { name: project.data.name })}
      </Anchor>
      <Group justify="space-between" align="flex-end">
        <Title order={2}>{t('documents.title')}</Title>
        <Button component={Link} to={`/projects/${projectId}/search`} variant="light">
          {t('documents.searchContent')}
        </Button>
      </Group>
      <ExportPanel projectId={projectId} />
      <Group align="flex-end">
        <TextInput
          label={t('documents.search')}
          value={search}
          onChange={(event) => setSearch(event.currentTarget.value)}
          maxLength={200}
          style={{ flex: 1, minWidth: 200 }}
        />
        <Select
          label={t('documents.folder')}
          placeholder={t('documents.allFolders')}
          clearable
          value={folder}
          onChange={setFolder}
          data={project.data.source_subpaths.map((subpath) => ({
            value: subpath === '' ? ROOT_FOLDER : subpath,
            label: folderLabel(subpath, root),
          }))}
        />
        <Select
          label={t('documents.status')}
          placeholder={t('documents.allStatuses')}
          clearable
          value={conversionStatus}
          onChange={(value) => setConversionStatus(value as ConversionStatus | null)}
          data={CONVERSION_STATUSES.map((status) => ({
            value: status,
            label: t(`documents.conversion.${status}`),
          }))}
        />
      </Group>
      {documents.isError && !documents.isFetchNextPageError ? (
        <ErrorAlert error={documents.error} />
      ) : documents.isPending ? (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      ) : total === 0 ? (
        <Text c="dimmed" role="status">
          {debounced || folder || conversionStatus ? t('documents.noMatches') : t('documents.empty')}
        </Text>
      ) : (
        <>
          <Text size="sm" role="status">
            {t('documents.total', { count: total, formatted: formatCount(total) })}
          </Text>
          <DocumentList
            // Una lista nueva por filtro: vuelve arriba y no pide páginas de los datos provisionales anteriores.
            key={`${debounced}|${folder ?? ''}|${conversionStatus ?? ''}`}
            projectId={projectId}
            rows={rows}
            total={total}
            root={root}
            hasMore={documents.hasNextPage && !documents.isPlaceholderData}
            loadMore={() => void documents.fetchNextPage()}
            loadingMore={documents.isFetchingNextPage}
            failed={documents.isFetchNextPageError}
          />
        </>
      )}
    </Stack>
  );
}

interface DocumentListProps {
  projectId: number;
  rows: DocumentOut[];
  total: number;
  root: string;
  hasMore: boolean;
  loadMore: () => void;
  loadingMore: boolean;
  /** La última página siguiente falló: no se vuelve a pedir sola (se ofrece «Reintentar»). */
  failed: boolean;
}

/** Lista virtualizada: solo se pintan las filas visibles; al acercarse al final pide la página siguiente. */
function DocumentList({
  projectId,
  rows,
  total,
  root,
  hasMore,
  loadMore,
  loadingMore,
  failed,
}: DocumentListProps) {
  const { t } = useTranslation();
  const parent = useRef<HTMLDivElement>(null);
  // El React Compiler no memoiza este componente (la API del virtualizador devuelve funciones): es lo esperado.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: rows.length + (hasMore ? 1 : 0),
    getScrollElement: () => parent.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });
  const items = virtualizer.getVirtualItems();
  const lastIndex = items.at(-1)?.index ?? 0;

  const needsMore = hasMore && !loadingMore && !failed && lastIndex >= rows.length - 1;
  useEffect(() => {
    if (needsMore) {
      loadMore();
    }
    // loadMore cambia en cada render; basta con reaccionar a needsMore.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsMore]);

  return (
    <Box
      ref={parent}
      role="list"
      aria-label={t('documents.title')}
      tabIndex={0}
      style={{ height: '60vh', overflow: 'auto', border: '1px solid var(--mantine-color-default-border)' }}
    >
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {items.map((item) => {
          const row = rows[item.index];
          return (
            <Box
              key={item.key}
              role="listitem"
              aria-setsize={total}
              aria-posinset={item.index + 1}
              px="sm"
              py={6}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: ROW_HEIGHT,
                transform: `translateY(${item.start}px)`,
                borderBottom: '1px solid var(--mantine-color-default-border)',
              }}
            >
              {row ? (
                <DocumentRow projectId={projectId} row={row} root={root} />
              ) : failed ? (
                <Button variant="subtle" size="xs" onClick={loadMore}>
                  {t('documents.retry')}
                </Button>
              ) : (
                <Loader size="sm" aria-label={t('common.loading')} />
              )}
            </Box>
          );
        })}
      </div>
    </Box>
  );
}

function DocumentRow({ projectId, row, root }: { projectId: number; row: DocumentOut; root: string }) {
  const { t } = useTranslation();
  const conversion = row.conversion_status ?? 'pending';
  return (
    <Group justify="space-between" wrap="nowrap" gap="sm" h="100%">
      <Stack gap={2} style={{ minWidth: 0, flex: 1 }}>
        <Text ff="monospace" size="sm" truncate="end" title={row.path}>
          {row.path}
        </Text>
        <Text size="xs" c="dimmed" truncate="end" title={row.error_message ?? undefined}>
          {folderLabel(row.folder, root)} · {formatDateTime(row.updated_at)}
          {row.error_message ? ` · ${row.error_message}` : ''}
        </Text>
      </Stack>
      <Group gap="xs" wrap="nowrap">
        <Badge color={STATUS_COLOR[conversion] ?? 'gray'} variant="light">
          {t(`documents.conversion.${conversion}`, { defaultValue: conversion })}
        </Badge>
        {row.output_path && (
          <Anchor
            component={Link}
            to={`/projects/${projectId}/documents/view?path=${encodeURIComponent(row.output_path)}`}
            size="sm"
            aria-label={t('documents.viewLabel', { path: row.path })}
          >
            {t('documents.view')}
          </Anchor>
        )}
      </Group>
    </Group>
  );
}
