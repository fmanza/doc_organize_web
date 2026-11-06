import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  TagsInput,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { SearchBox, SortableTh } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { formatCount, formatDateTime } from '../../components/format';
import { useAiStatus } from '../admin/useAi';
import { DangerousOperationModal } from '../projects/DangerousOperationModal';
import { canDo, type ProjectOut, useEnqueueRun, useProject } from '../projects/useProjects';
import {
  aiFamily,
  buildParams,
  type Catalog,
  type ContextOut,
  type DocumentFilter,
  type ContextDocumentSort,
  MAX_TEMPLATE_BYTES,
  useContextDocuments,
  useManifest,
  useProjectContext,
  useSaveManifest,
  useTaxonomyDraft,
  useTemplates,
} from './useContext';

/**
 * Contexto del proyecto (sustituye a `context.html.j2`): construir (dominios descubiertos, catálogo propio, plantilla o
 * manifiesto), ver dominios y documentos, editar el manifiesto de taxonomía, abrir el sitio aislado y borrar. Con la
 * Fase 8, también clasificar con IA lo que las reglas dejan sin clasificar y pedir un borrador del manifiesto.
 */
const CONTEXT_DOCUMENT_SORT: readonly ContextDocumentSort[] = [
  'title',
  'path',
  'document_type',
  'organized_path',
];

export function ContextPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const context = useProjectContext(projectId);
  const [deleting, setDeleting] = useState(false);

  if (project.isPending || context.isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (project.isError) {
    return <ErrorAlert error={project.error} />;
  }
  if (context.isError) {
    return <ErrorAlert error={context.error} />;
  }
  const built = context.data;
  const writable = project.data.destination_location.access === 'rw';

  return (
    <Stack>
      <Anchor component={Link} to={`/projects/${projectId}`} size="sm">
        {t('context.back', { name: project.data.name })}
      </Anchor>
      <Title order={2}>{t('context.title')}</Title>
      <Text c="dimmed">{t('context.intro')}</Text>

      {built ? (
        <Summary
          context={built}
          projectId={projectId}
          canDelete={canDo(project.data, 'owner') && writable}
          onDelete={() => setDeleting(true)}
        />
      ) : (
        <Text c="dimmed" role="status">
          {t('context.empty')}
        </Text>
      )}

      {canDo(project.data, 'editor') &&
        (writable ? (
          <BuildCard key={built?.built_at ?? 'nuevo'} project={project.data} context={built} />
        ) : (
          <Alert color="gray">{t('context.readOnly')}</Alert>
        ))}

      {built && <Domains key={built.built_at} context={built} projectId={projectId} />}

      <ManifestCard projectId={projectId} editable={canDo(project.data, 'editor') && writable} />

      {deleting && (
        <DangerousOperationModal
          project={project.data}
          operation="context_delete"
          onClose={() => setDeleting(false)}
        />
      )}
    </Stack>
  );
}

function Summary({
  context,
  projectId,
  canDelete,
  onDelete,
}: {
  context: ContextOut;
  projectId: number;
  canDelete: boolean;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const stats: [string, number][] = [
    ['domains', context.domains.length],
    ['documents', context.documents_count],
    ['unclassified', context.unclassified_count],
    ['failed', context.failed_count],
    ['collisions', context.collisions_count],
  ];
  return (
    <Card withBorder>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {t('context.summary.title', { date: formatDateTime(context.built_at) })}
        </Title>
        {context.built_by_run_id && (
          <Anchor component={Link} to={`/runs/${context.built_by_run_id}`} size="sm">
            {t('context.summary.openRun')}
          </Anchor>
        )}
      </Group>
      <Text size="sm" mb="xs">
        {t('context.summary.folder', { folder: context.output_folder_name })} ·{' '}
        {t(`context.catalog.${context.catalog_kind}`, { defaultValue: context.catalog_kind })}
        {context.taxonomy_template_name ? ` «${context.taxonomy_template_name}»` : ''}
        {context.ai_classification && (
          <Badge ml="xs" size="sm" variant="light" color="grape">
            {t('context.ai.badge')}
          </Badge>
        )}
      </Text>
      <SimpleGrid cols={{ base: 2, sm: 5 }} spacing="xs" component="dl">
        {stats.map(([key, value]) => (
          <div key={key}>
            <Text size="xs" c="dimmed" component="dt">
              {t(`context.summary.${key}`)}
            </Text>
            <Text component="dd" m={0}>
              {formatCount(value)}
            </Text>
          </div>
        ))}
      </SimpleGrid>
      {context.failed_count > 0 && (
        <Alert color="orange" mt="sm">
          {t('context.warnings.failed', { count: context.failed_count })}
        </Alert>
      )}
      {context.collisions_count > 0 && (
        <Alert color="orange" mt="sm">
          {t('context.warnings.collisions', { count: context.collisions_count })}
        </Alert>
      )}
      {!context.site_built && (
        <Alert color="gray" mt="sm">
          {t('context.warnings.noSite')}
        </Alert>
      )}
      <Group mt="sm">
        {context.site_built && (
          <Button component={Link} to={`/projects/${projectId}/context/site`}>
            {t('context.site.open')}
          </Button>
        )}
        {canDelete && (
          <Button color="red" variant="light" onClick={onDelete}>
            {t('projects.danger.context_delete.button')}
          </Button>
        )}
      </Group>
    </Card>
  );
}

function BuildCard({ project, context }: { project: ProjectOut; context: ContextOut | null }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const enqueue = useEnqueueRun(project.id);
  const templates = useTemplates();
  const [catalog, setCatalog] = useState<Catalog>(
    (context?.catalog_kind as Catalog | undefined) ?? 'discover',
  );
  const [domains, setDomains] = useState<string[]>([]);
  const [template, setTemplate] = useState<string | null>(context?.taxonomy_template_name ?? null);
  const [folder, setFolder] = useState('organizado');
  const [threshold, setThreshold] = useState(0.5);
  const [buildSite, setBuildSite] = useState(true);
  const status = useAiStatus();
  const [withAi, setWithAi] = useState(false);
  const aiAvailable = status.data?.[aiFamily(catalog)] === true;

  const ready =
    (catalog !== 'domains' || domains.length > 0) && (catalog !== 'template' || template !== null);
  const launch = () =>
    enqueue.mutate(
      buildParams({
        catalog,
        domains: catalog === 'domains' ? domains : [],
        template_name: catalog === 'template' ? template : null,
        output_folder_name: context ? null : folder.trim() || null,
        threshold,
        build_site: buildSite,
        ai_classification: withAi && aiAvailable,
      }),
      { onSuccess: (run) => void navigate(`/runs/${run.id}`) },
    );

  return (
    <Card withBorder>
      <Title order={3} size="h4" mb="xs">
        {t(context ? 'context.build.rebuildTitle' : 'context.build.title')}
      </Title>
      <Stack>
        <SegmentedControl
          value={catalog}
          onChange={(value) => setCatalog(value as Catalog)}
          aria-label={t('context.build.catalog')}
          data={(['discover', 'domains', 'template', 'manifest'] as const).map((value) => ({
            value,
            label: t(`context.catalog.${value}`),
          }))}
        />
        <Text size="sm" c="dimmed">
          {t(`context.build.help.${catalog}`)}
        </Text>
        {catalog === 'domains' && (
          <TagsInput
            label={t('context.build.domains')}
            description={t('context.build.domainsHelp')}
            value={domains}
            onChange={setDomains}
            maxTags={100}
            clearable
          />
        )}
        {catalog === 'template' && (
          <Select
            label={t('context.build.template')}
            data={(templates.data ?? []).map((item) => ({
              value: item.name,
              label: item.title ? `${item.title} (${item.name})` : item.name,
            }))}
            value={template}
            onChange={setTemplate}
            searchable
            nothingFoundMessage={t('context.build.noTemplates')}
          />
        )}
        {templates.isError && catalog === 'template' && <ErrorAlert error={templates.error} />}
        <Group align="flex-end">
          {context ? (
            <Text size="sm">{t('context.build.folderFixed', { folder: context.output_folder_name })}</Text>
          ) : (
            <TextInput
              label={t('context.build.folder')}
              description={t('context.build.folderHelp')}
              value={folder}
              maxLength={120}
              onChange={(event) => setFolder(event.currentTarget.value)}
            />
          )}
          <NumberInput
            label={t('context.build.threshold')}
            min={0}
            max={1}
            step={0.05}
            decimalScale={2}
            clampBehavior="strict"
            value={threshold}
            onChange={(value) => setThreshold(typeof value === 'number' ? value : 0.5)}
            w={160}
          />
          <Switch
            label={t('context.build.site')}
            checked={buildSite}
            onChange={(event) => setBuildSite(event.currentTarget.checked)}
          />
        </Group>
        <Switch
          label={t('context.ai.classify')}
          description={t(
            aiAvailable ? 'context.ai.classifyHelp' : `context.ai.notConfigured.${aiFamily(catalog)}`,
          )}
          checked={withAi && aiAvailable}
          disabled={!aiAvailable}
          onChange={(event) => setWithAi(event.currentTarget.checked)}
        />
        {withAi && aiAvailable && (
          <Alert color="grape" title={t('context.ai.egressTitle')}>
            {t('context.ai.egress')}
          </Alert>
        )}
        {enqueue.isError && <ErrorAlert error={enqueue.error} />}
        <Group justify="flex-end">
          <Button onClick={launch} loading={enqueue.isPending} disabled={!ready}>
            {t(context ? 'context.build.rebuild' : 'context.build.run')}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}

/** Fila del dominio que se está viendo. */
const SELECTED = { bg: 'var(--mantine-color-default-hover)' } as const;

function Domains({ context, projectId }: { context: ContextOut; projectId: number }) {
  const { t } = useTranslation();
  const [domain, setDomain] = useState<string | null>(context.domains[0]?.slug ?? null);
  const [only, setOnly] = useState<DocumentFilter | null>(null);
  const list = useListState(CONTEXT_DOCUMENT_SORT, 'doc');
  const documents = useContextDocuments(projectId, domain, only, list.query);
  const select = (slug: string | null) => {
    setDomain(slug);
    list.paging.setPage(1, true);
  };

  return (
    <Card withBorder>
      <Title order={3} size="h4" mb="xs">
        {t('context.domains.title')}
      </Title>
      <Table.ScrollContainer minWidth={480}>
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('context.domains.name')}</Table.Th>
              <Table.Th>{t('context.domains.status')}</Table.Th>
              <Table.Th>{t('context.domains.documents')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {context.domains.map((item) => (
              <Table.Tr key={item.slug} {...(item.slug === domain ? SELECTED : {})}>
                <Table.Td>
                  <Anchor
                    component="button"
                    type="button"
                    aria-pressed={item.slug === domain}
                    onClick={() => select(item.slug)}
                  >
                    {item.name}
                  </Anchor>
                  {item.description && (
                    <Text size="xs" c="dimmed">
                      {item.description}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color={item.status === 'confirmado' ? 'teal' : 'gray'}>
                    {t(`context.domains.statuses.${item.status}`, { defaultValue: item.status })}
                  </Badge>
                </Table.Td>
                <Table.Td>{formatCount(item.documents)}</Table.Td>
              </Table.Tr>
            ))}
            <Table.Tr {...(domain === null ? SELECTED : {})}>
              <Table.Td>
                <Anchor
                  component="button"
                  type="button"
                  aria-pressed={domain === null}
                  onClick={() => select(null)}
                >
                  {t('context.domains.unclassified')}
                </Anchor>
              </Table.Td>
              <Table.Td />
              <Table.Td>{formatCount(context.unclassified_count)}</Table.Td>
            </Table.Tr>
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      <Group justify="space-between" mt="md" mb="xs">
        <Title order={4} size="h5">
          {domain === null
            ? t('context.domains.unclassified')
            : (context.domains.find((d) => d.slug === domain)?.name ?? domain)}
        </Title>
        <SegmentedControl
          size="xs"
          value={only ?? 'all'}
          aria-label={t('context.documents.filter')}
          onChange={(value) => {
            setOnly(value === 'all' ? null : (value as DocumentFilter));
            list.paging.setPage(1, true);
          }}
          data={[
            { value: 'all', label: t('context.documents.all') },
            { value: 'failed', label: t('context.documents.failed') },
            { value: 'collision', label: t('context.documents.collision') },
          ]}
        />
      </Group>
      <SearchBox value={list.q} onChange={list.setQ} label={t('context.documents.search')} />
      {documents.isError ? (
        <ErrorAlert error={documents.error} />
      ) : !documents.data ? (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      ) : documents.data.total === 0 ? (
        <Text c="dimmed" role="status">
          {t(list.q ? 'listing.empty' : 'context.documents.empty')}
        </Text>
      ) : (
        <>
          <Text size="sm" role="status">
            {t('context.documents.total', {
              count: documents.data.total,
              formatted: formatCount(documents.data.total),
            })}
          </Text>
          <Table.ScrollContainer minWidth={640}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <SortableTh state={list} sortKey="title">
                    {t('context.documents.title')}
                  </SortableTh>
                  <SortableTh state={list} sortKey="path">
                    {t('context.documents.original')}
                  </SortableTh>
                  <SortableTh state={list} sortKey="document_type">
                    {t('context.documents.type')}
                  </SortableTh>
                  <SortableTh state={list} sortKey="organized_path">
                    {t('context.documents.copy')}
                  </SortableTh>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {documents.data.items.map((doc) => {
                  const original = doc.folder ? `${doc.folder}/${doc.path}` : doc.path;
                  return (
                    <Table.Tr key={original}>
                      <Table.Td>
                        <Text size="sm">{doc.title}</Text>
                        {doc.output_path && (
                          <Anchor
                            component={Link}
                            to={`/projects/${projectId}/documents/view?path=${encodeURIComponent(doc.output_path)}`}
                            size="xs"
                          >
                            {t('context.documents.view')}
                          </Anchor>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Text ff="monospace" size="sm" style={{ wordBreak: 'break-all' }}>
                          {original}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {doc.material_type_name ?? doc.material_type ?? doc.document_type ?? '—'}
                        {doc.classified_by === 'ai' && (
                          <Badge ml="xs" size="xs" variant="light" color="grape" title={t('context.ai.byAi')}>
                            {t('context.ai.badge')}
                          </Badge>
                        )}
                      </Table.Td>
                      <Table.Td>
                        {doc.failed ? (
                          <Badge color="red" variant="light">
                            {t('context.documents.notCopied')}
                          </Badge>
                        ) : doc.collision ? (
                          <Badge color="orange" variant="light" title={doc.organized_path ?? undefined}>
                            {t('context.documents.overwritten')}
                          </Badge>
                        ) : (
                          <Text ff="monospace" size="xs" style={{ wordBreak: 'break-all' }}>
                            {doc.organized_path ?? '—'}
                          </Text>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <PageControls state={list.paging} total={documents.data.total} label={t('paging.label')} />
        </>
      )}
    </Card>
  );
}

function ManifestCard({ projectId, editable }: { projectId: number; editable: boolean }) {
  const { t } = useTranslation();
  const manifest = useManifest(projectId);
  const save = useSaveManifest(projectId);
  const [draft, setDraft] = useState<string | null>(null);

  if (manifest.isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (manifest.isError) {
    return <ErrorAlert error={manifest.error} />;
  }
  const text = draft ?? manifest.data.markdown ?? '';
  const tooLarge = new TextEncoder().encode(text).length > MAX_TEMPLATE_BYTES;
  return (
    <Card withBorder>
      <Title order={3} size="h4" mb="xs">
        {t('context.manifest.title')}
      </Title>
      <Text size="sm" c="dimmed" mb="xs">
        {t('context.manifest.intro')}
      </Text>
      {manifest.data.error && (
        <Alert color="orange" mb="xs" title={t('context.manifest.invalid')}>
          {manifest.data.error}
        </Alert>
      )}
      {manifest.data.markdown !== null && !manifest.data.error && (
        <Text size="sm" mb="xs">
          {t('context.manifest.catalog', {
            domains: manifest.data.domains.length,
            materials: manifest.data.material_types.length,
          })}
        </Text>
      )}
      {editable && <DraftPanel projectId={projectId} onDraft={setDraft} />}
      <Textarea
        label={t('context.manifest.markdown')}
        value={text}
        onChange={(event) => setDraft(event.currentTarget.value)}
        readOnly={!editable}
        rows={10}
        resize="vertical"
        styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
        error={tooLarge ? t('context.manifest.tooLarge') : undefined}
      />
      {save.isError && <ErrorAlert error={save.error} mt="xs" />}
      {save.isSuccess && draft === null && (
        <Text size="sm" c="teal" role="status" mt="xs">
          {t('context.manifest.saved')}
        </Text>
      )}
      {editable && (
        <Group justify="flex-end" mt="xs">
          <Button
            onClick={() => save.mutate(text, { onSuccess: () => setDraft(null) })}
            loading={save.isPending}
            disabled={draft === null || !text.trim() || tooLarge}
          >
            {t('context.manifest.save')}
          </Button>
        </Group>
      )}
    </Card>
  );
}

/**
 * Borrador del manifiesto con IA: lanza el run `taxonomy_draft`, espera a que termine y carga el Markdown en el
 * editor **sin guardarlo** (se revisa y se guarda con «Guardar manifiesto»).
 */
function DraftPanel({ projectId, onDraft }: { projectId: number; onDraft: (markdown: string) => void }) {
  const { t } = useTranslation();
  const status = useAiStatus();
  const [sampleSize, setSampleSize] = useState(25);
  const draft = useTaxonomyDraft(projectId, onDraft);
  const available = status.data?.litellm_taxonomy_manifest_draft === true;

  return (
    <Card withBorder mb="sm" component="section" aria-label={t('context.ai.draftTitle')}>
      <Text fw={500} size="sm">
        {t('context.ai.draftTitle')}
      </Text>
      <Text size="xs" c="dimmed" mb="xs">
        {t(available ? 'context.ai.draftHelp' : 'context.ai.notConfigured.litellm_taxonomy_manifest_draft')}
      </Text>
      <Group align="flex-end">
        <NumberInput
          label={t('context.ai.sampleSize')}
          min={1}
          max={60}
          allowDecimal={false}
          clampBehavior="strict"
          value={sampleSize}
          onChange={(value) => setSampleSize(typeof value === 'number' ? value : 25)}
          w={180}
          disabled={!available}
        />
        <Button
          variant="light"
          color="grape"
          onClick={() => draft.start(sampleSize)}
          loading={draft.running}
          disabled={!available}
        >
          {t('context.ai.draft')}
        </Button>
        {draft.runId && (
          <Anchor component={Link} to={`/runs/${draft.runId}`} size="sm">
            {t('context.ai.openRun')}
          </Anchor>
        )}
      </Group>
      {draft.error && <ErrorAlert error={draft.error} mt="xs" />}
      {draft.failure && (
        <Alert color="red" role="alert" mt="xs">
          {draft.failure}
        </Alert>
      )}
      {draft.loaded && (
        <Alert color="grape" role="status" mt="xs" title={t('context.ai.draftLoaded')}>
          {draft.loaded.reasoning ?? t('context.ai.draftLoadedBody')}
          <Text size="xs" mt={4}>
            {t('context.ai.draftSample', {
              sample: draft.loaded.sample_documents,
              total: draft.loaded.total_documents,
            })}
          </Text>
        </Alert>
      )}
    </Card>
  );
}
