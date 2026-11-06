import {
  Alert,
  Anchor,
  Badge,
  Button,
  Center,
  FileButton,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { SearchBox, SortableTh } from '../../components/listing';
import { useClientTable } from '../../components/useListState';
import { formatDateTime } from '../../components/format';
import {
  MAX_TEMPLATE_BYTES,
  nameFromFile,
  type TaxonomyTemplate,
  TEMPLATE_NAME,
  templateDownloadUrl,
  useDeleteTemplate,
  useSaveTemplate,
  useTemplate,
  useTemplates,
} from '../context/useContext';

/** Lo que se edita: plantilla nueva (con su nombre) o existente (nombre fijo); `source` para duplicar o importar. */
interface Editing {
  name: string;
  fixedName: boolean;
  source?: string;
  markdown?: string;
}

/**
 * Plantillas de taxonomía (sustituye a `taxonomy_templates_admin.html.j2`): las incluidas en doc_organize son de solo
 * lectura y se pueden duplicar; las personalizadas se crean, editan, importan y exportan como Markdown.
 */
const TEMPLATE_COLUMNS = {
  name: (item: TaxonomyTemplate) => item.name,
  title: (item: TaxonomyTemplate) => item.title,
  updated: (item: TaxonomyTemplate) => item.updated_at,
};

export function TaxonomyTemplatesPage() {
  const { t } = useTranslation();
  const templates = useTemplates();
  const remove = useDeleteTemplate();
  const [editing, setEditing] = useState<Editing | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const table = useClientTable(
    templates.data,
    TEMPLATE_COLUMNS,
    (item) => `${item.name} ${item.title ?? ''} ${item.description ?? ''}`,
  );

  const importFile = (file: File | null) => {
    setImportError(null);
    if (!file) return;
    if (file.size > MAX_TEMPLATE_BYTES) {
      setImportError(t('templates.import.tooLarge'));
      return;
    }
    void file.text().then(
      (markdown) => setEditing({ name: nameFromFile(file.name), fixedName: false, markdown }),
      () => setImportError(t('templates.import.unreadable')),
    );
  };

  if (templates.isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (templates.isError) {
    return <ErrorAlert error={templates.error} />;
  }
  return (
    <Stack>
      <Title order={2}>{t('templates.title')}</Title>
      <Text c="dimmed">{t('templates.intro')}</Text>
      <Group>
        <Button onClick={() => setEditing({ name: '', fixedName: false, markdown: '' })}>
          {t('templates.new')}
        </Button>
        <FileButton onChange={importFile} accept=".md,text/markdown,text/plain">
          {(props) => (
            <Button variant="light" {...props}>
              {t('templates.import.button')}
            </Button>
          )}
        </FileButton>
      </Group>
      {importError && (
        <Alert color="red" role="alert">
          {importError}
        </Alert>
      )}
      <SearchBox value={table.q} onChange={table.setQ} label={t('templates.search')} />
      <Table.ScrollContainer minWidth={640}>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <SortableTh state={table} sortKey="name">
                {t('templates.fields.name')}
              </SortableTh>
              <SortableTh state={table} sortKey="title">
                {t('templates.fields.title')}
              </SortableTh>
              <SortableTh state={table} sortKey="updated">
                {t('templates.fields.updated')}
              </SortableTh>
              <Table.Th>{t('common.actions')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {table.pageRows.map((item) => (
              <TemplateRow
                key={item.name}
                item={item}
                onEdit={() => setEditing({ name: item.name, fixedName: true })}
                onDuplicate={() =>
                  setEditing({ name: `${item.name}-copia`, fixedName: false, source: item.name })
                }
                onDelete={() => {
                  remove.reset();
                  setDeleting(item.name);
                }}
              />
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      <PageControls state={table.paging} total={table.total} label={t('paging.label')} />
      {editing && (
        <TemplateEditor
          editing={editing}
          taken={templates.data.map((item) => item.name)}
          onClose={() => setEditing(null)}
        />
      )}
      <Modal
        opened={deleting !== null}
        onClose={() => {
          remove.reset();
          setDeleting(null);
        }}
        title={t('templates.delete.title', { name: deleting })}
      >
        <Stack>
          <Text>{t('templates.delete.body')}</Text>
          {remove.isError && <ErrorAlert error={remove.error} />}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleting(null)}>
              {t('common.cancel')}
            </Button>
            <Button
              color="red"
              loading={remove.isPending}
              onClick={() => deleting && remove.mutate(deleting, { onSuccess: () => setDeleting(null) })}
            >
              {t('templates.delete.confirm')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

function TemplateRow({
  item,
  onEdit,
  onDuplicate,
  onDelete,
}: {
  item: TaxonomyTemplate;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Table.Tr>
      <Table.Td>
        <Group gap="xs">
          <Text ff="monospace" size="sm">
            {item.name}
          </Text>
          {item.builtin && (
            <Badge variant="light" color="gray">
              {t('templates.builtin')}
            </Badge>
          )}
        </Group>
      </Table.Td>
      <Table.Td>
        <Text size="sm">{item.title ?? '—'}</Text>
        {item.description && (
          <Text size="xs" c="dimmed">
            {item.description}
          </Text>
        )}
      </Table.Td>
      <Table.Td>{item.updated_at ? formatDateTime(item.updated_at) : '—'}</Table.Td>
      <Table.Td>
        <Group gap="xs" wrap="nowrap">
          {item.builtin ? (
            <Button
              size="xs"
              variant="default"
              onClick={onDuplicate}
              aria-label={t('templates.duplicateNamed', { name: item.name })}
            >
              {t('templates.duplicate')}
            </Button>
          ) : (
            <Button
              size="xs"
              variant="default"
              onClick={onEdit}
              aria-label={t('templates.editNamed', { name: item.name })}
            >
              {t('common.edit')}
            </Button>
          )}
          <Anchor
            href={templateDownloadUrl(item.name)}
            size="sm"
            aria-label={t('templates.downloadNamed', { name: item.name })}
          >
            {t('templates.download')}
          </Anchor>
          {!item.builtin && (
            <Button
              size="xs"
              color="red"
              variant="subtle"
              onClick={onDelete}
              aria-label={t('templates.deleteNamed', { name: item.name })}
            >
              {t('common.delete')}
            </Button>
          )}
        </Group>
      </Table.Td>
    </Table.Tr>
  );
}

function TemplateEditor({
  editing,
  taken,
  onClose,
}: {
  editing: Editing;
  /** Nombres en uso: crear, duplicar o importar no sobrescribe una plantilla existente sin querer. */
  taken: string[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const save = useSaveTemplate();
  // Al editar o duplicar se parte del Markdown guardado; al crear o importar, del que trae `editing`.
  const loaded = useTemplate(editing.markdown === undefined ? (editing.source ?? editing.name) : null);
  const [name, setName] = useState(editing.name);
  const [draft, setDraft] = useState<string | null>(editing.markdown ?? null);

  const markdown = draft ?? loaded.data?.markdown ?? '';
  const nameTaken = !editing.fixedName && taken.includes(name);
  const nameValid = TEMPLATE_NAME.test(name) && !nameTaken;
  const tooLarge = new TextEncoder().encode(markdown).length > MAX_TEMPLATE_BYTES;
  return (
    <Modal
      opened
      onClose={onClose}
      size="xl"
      title={editing.fixedName ? t('templates.editTitle', { name }) : t('templates.newTitle')}
    >
      <Stack>
        <TextInput
          label={t('templates.fields.name')}
          description={t('templates.nameHelp')}
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
          disabled={editing.fixedName}
          error={
            nameTaken ? t('templates.nameTaken') : name && !nameValid ? t('templates.nameInvalid') : undefined
          }
          maxLength={64}
        />
        {loaded.isError && <ErrorAlert error={loaded.error} />}
        {loaded.isPending && loaded.fetchStatus !== 'idle' && draft === null ? (
          <Center>
            <Loader aria-label={t('common.loading')} />
          </Center>
        ) : (
          <Textarea
            label={t('templates.fields.markdown')}
            description={t('templates.markdownHelp')}
            value={markdown}
            onChange={(event) => setDraft(event.currentTarget.value)}
            rows={18}
            resize="vertical"
            styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
            error={tooLarge ? t('context.manifest.tooLarge') : undefined}
          />
        )}
        {save.isError && <ErrorAlert error={save.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            loading={save.isPending}
            disabled={!nameValid || !markdown.trim() || tooLarge}
            onClick={() => save.mutate({ name, markdown }, { onSuccess: onClose })}
          >
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
