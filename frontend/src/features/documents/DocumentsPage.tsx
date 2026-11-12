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
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatCount, formatDateTime } from '../../components/format';
import { PageControls } from '../../components/Paging';
import { ClearSection, SortSelect } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { useProject } from '../projects/useProjects';
import { ExportPanel } from './ExportPanel';
import {
  CONVERSION_STATUSES,
  type ConversionStatus,
  type DocumentOut,
  type DocumentSort,
  ROOT_FOLDER,
  useDocuments,
} from './useDocuments';

const DOCUMENT_SORT: readonly DocumentSort[] = [
  'path',
  'updated_at',
  'conversion_status',
  'error_retry_count',
];

const STATUS_COLOR: Record<string, string> = { success: 'green', error: 'red' };

function folderLabel(folder: string, root: string): string {
  return folder === '' ? root : folder;
}

/**
 * Documentos del proyecto (caché de doc_organize, sustituye al visor de caché de `dashboard.html.j2`): lista paginada
 * en servidor con la página en la URL (100 000 documentos, Fase 10), búsqueda en la ruta, filtros, visor y exportaciones.
 */
export function DocumentsPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const [search, setSearch] = useState('');
  const [debounced] = useDebouncedValue(search.trim(), 300);
  const [folder, setFolder] = useState<string | null>(null);
  const [conversionStatus, setConversionStatus] = useState<ConversionStatus | null>(null);
  // web 1.3.0: orden por columna (doc_organize 1.2.0, G40); la búsqueda sigue siendo la del nombre o subcarpeta.
  const list = useListState(DOCUMENT_SORT);
  const { paging } = list;
  const documents = useDocuments(projectId, { search: debounced, folder, conversionStatus }, list.query);

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
  const rows = documents.data?.items ?? [];
  const total = documents.data?.total ?? 0;

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
          label={t('listing.searchLabel')}
          aria-label={t('documents.search')}
          placeholder={t('documents.search')}
          value={search}
          onChange={(event) => {
            // Otro filtro: la página 7 de la búsqueda anterior no tiene sentido en la nueva.
            setSearch(event.currentTarget.value);
            paging.setPage(1, true);
          }}
          maxLength={200}
          rightSectionPointerEvents="auto"
          rightSection={
            <ClearSection
              text={search}
              onClear={() => {
                setSearch('');
                paging.setPage(1, true);
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
            paging.setPage(1, true);
          }}
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
          onChange={(value) => {
            setConversionStatus(value as ConversionStatus | null);
            paging.setPage(1, true);
          }}
          data={CONVERSION_STATUSES.map((status) => ({
            value: status,
            label: t(`documents.conversion.${status}`),
          }))}
        />
        <SortSelect
          state={list}
          label={t('listing.sortLabel')}
          options={DOCUMENT_SORT.map((value) => ({ value, label: t(`documents.sort.${value}`) }))}
        />
      </Group>
      {documents.isError ? (
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
          <DocumentList projectId={projectId} rows={rows} root={root} />
          <PageControls state={paging} total={total} label={t('documents.pages')} />
        </>
      )}
    </Stack>
  );
}

/** Una página de documentos (como mucho 100 filas: sin virtualizar). */
function DocumentList({ projectId, rows, root }: { projectId: number; rows: DocumentOut[]; root: string }) {
  const { t } = useTranslation();
  return (
    <Stack
      component="ul"
      gap={0}
      aria-label={t('documents.title')}
      p={0}
      m={0}
      style={{ listStyle: 'none', border: '1px solid var(--mantine-color-default-border)' }}
    >
      {rows.map((row) => (
        <Box
          component="li"
          key={`${row.folder}/${row.path}`}
          px="sm"
          py={6}
          style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
        >
          <DocumentRow projectId={projectId} row={row} root={root} />
        </Box>
      ))}
    </Stack>
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
