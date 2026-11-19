import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Modal,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  TagsInput,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import { BackLink } from '../../components/BackLink';
import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { SearchBox, SortableTh } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { formatCount, formatDateTime } from '../../components/format';
import { useAiStatus } from '../admin/useAi';
import { DangerousOperationModal } from '../projects/DangerousOperationModal';
import { canDo, type ProjectOut, useEnqueueRun, useProject } from '../projects/useProjects';
import {
  aiTask,
  buildParams,
  type Catalog,
  CONTEXT_HISTORY_XLSX,
  type ContextBuild,
  type ContextDocument,
  type ContextOut,
  type DocumentFilter,
  initialSelection,
  sameText,
  type Selection,
  type ContextDocumentSort,
  type Manifest,
  manifestKey,
  manifestQuery,
  templateQuery,
  useContextDocuments,
  useContextHistory,
  useProjectContext,
  useTemplates,
} from './useContext';
import { AxisBadges, AxisEvidence, AxisFilters } from './Axes';
import { ManifestCard } from './ManifestCard';
import { ProfileCard } from './ProfileCard';

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

/** Copia de una plantilla al borrador del manifiesto, con lo que había antes para «Deshacer». */
interface Copied {
  name: string;
  previous: { draft: string | null; selection: Selection };
}

export function ContextPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const context = useProjectContext(projectId);
  const queryClient = useQueryClient();
  const [deleting, setDeleting] = useState(false);
  // Selección derivada de `built_at` sin efectos (A4): al terminar una construcción vuelve a la del contexto nuevo.
  const [chosen, setChosen] = useState<Selection & { builtAt: string | null }>({
    builtAt: null,
    ...initialSelection(null),
  });
  const [draft, setDraft] = useState<string | null>(null);
  const [copied, setCopied] = useState<Copied | null>(null);
  const [confirm, setConfirm] = useState<{ body: string; apply: () => void } | null>(null);
  const [focusToken, setFocusToken] = useState(0);
  const [showManifest, setShowManifest] = useState(false);
  const [copyError, setCopyError] = useState<unknown>(null);

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
  const builtAt = built?.built_at ?? null;
  const selection: Selection = chosen.builtAt === builtAt ? chosen : initialSelection(built);
  const select = (next: Selection) => setChosen({ builtAt, ...next });
  const writable = project.data.destination_location.access === 'rw';
  const canBuild = canDo(project.data, 'editor') && writable;
  const savedManifest = queryClient.getQueryData<Manifest>(manifestKey(projectId))?.markdown ?? null;
  const manifestDirty = draft !== null && !sameText(draft, savedManifest);

  /** Sustituye el borrador; si hay otro texto (borrador o guardado), pide confirmación antes (A6, B6). */
  const replaceDraft = (markdown: string, body: string, apply: () => void) => {
    const current = draft ?? queryClient.getQueryData<Manifest>(manifestKey(projectId))?.markdown ?? null;
    if (current && !sameText(current, markdown)) {
      setConfirm({ body, apply });
    } else {
      apply();
    }
  };

  /** «Personalizar para este proyecto»: copia la plantilla al borrador del manifiesto (nunca guarda). */
  const copyTemplateToManifest = (name: string) => {
    setCopyError(null);
    Promise.all([
      queryClient.ensureQueryData(templateQuery(name)),
      queryClient.ensureQueryData(manifestQuery(projectId)),
    ])
      .then(([template]) =>
        replaceDraft(template.markdown, t('context.manifest.replaceBody', { name }), () => {
          setCopied({ name, previous: { draft, selection } });
          setDraft(template.markdown);
          select({ catalog: 'manifest', template: selection.template });
          setFocusToken((token) => token + 1);
        }),
      )
      .catch(setCopyError);
  };

  const manifestCard = (editable: boolean) => (
    <ManifestCard
      projectId={projectId}
      editable={editable}
      context={built}
      draft={draft}
      onDraftChange={(markdown) => {
        setDraft(markdown);
        if (markdown === null) {
          setCopied(null);
        }
      }}
      onReplace={(markdown, body) =>
        replaceDraft(markdown, body, () => {
          setCopied(null);
          setDraft(markdown);
        })
      }
      copiedFrom={copied?.name ?? null}
      onUndoCopy={() => {
        if (copied) {
          setDraft(copied.previous.draft);
          select(copied.previous.selection);
          setCopied(null);
        }
      }}
      focusToken={focusToken}
    />
  );

  return (
    <Stack>
      <BackLink to={`/projects/${projectId}`}>{t('context.back', { name: project.data.name })}</BackLink>
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

      {built?.freshness && <FreshnessBanner freshness={built.freshness} canBuild={canBuild} />}

      {canDo(project.data, 'editor') && !writable && <Alert color="gray">{t('context.readOnly')}</Alert>}
      {canBuild && (
        <BuildCard
          key={builtAt ?? 'nuevo'}
          project={project.data}
          context={built}
          selection={selection}
          onSelectionChange={select}
          manifestDirty={manifestDirty}
          onUseTemplate={copyTemplateToManifest}
          copyError={copyError}
        />
      )}
      {canBuild && selection.catalog === 'manifest' && manifestCard(true)}
      {!canBuild &&
        (built?.catalog_kind === 'manifest' || showManifest ? (
          manifestCard(false)
        ) : (
          <Anchor component="button" onClick={() => setShowManifest(true)} w="fit-content">
            {t('context.manifest.show')}
          </Anchor>
        ))}

      <ProfileCard projectId={projectId} editable={canBuild} selection={selection} />

      {built && <Domains key={built.built_at} context={built} projectId={projectId} />}

      <HistoryCard projectId={projectId} />

      {deleting && (
        <DangerousOperationModal
          project={project.data}
          operation="context_delete"
          onClose={() => setDeleting(false)}
        />
      )}
      <Modal
        opened={confirm !== null}
        onClose={() => setConfirm(null)}
        title={t('context.manifest.replaceTitle')}
      >
        <Stack>
          <Text>{confirm?.body}</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirm(null)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={() => {
                confirm?.apply();
                setConfirm(null);
              }}
            >
              {t('context.manifest.replace')}
            </Button>
          </Group>
        </Stack>
      </Modal>
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
      <Traceability context={context} />
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

/** Versión de doc_organize y modelos de IA de la construcción (1.5.0); nada en contextos anteriores. */
function Traceability({ context }: { context: ContextOut }) {
  const { t } = useTranslation();
  const parts = [
    context.built_with_version && t('context.trace.version', { version: context.built_with_version }),
    context.ai_classification_model &&
      t('context.trace.classificationModel', { model: context.ai_classification_model }),
    context.ai_enrichment_model && t('context.trace.enrichmentModel', { model: context.ai_enrichment_model }),
  ].filter(Boolean);
  if (parts.length === 0) {
    return null;
  }
  return (
    <Text size="xs" c="dimmed" mb="xs">
      {parts.join(' · ')}
    </Text>
  );
}

/** Ancla de la tarjeta de construcción (el aviso de frescura lleva a ella). */
const BUILD_CARD_ID = 'construir-contexto';
type Freshness = NonNullable<ContextOut['freshness']>;

/**
 * Aviso de frescura (W4, `check_context_freshness`): el contexto ya no refleja la caché del último escaneo. Con los
 * recuentos, unos ejemplos y, si puede construir, el enlace para reconstruir.
 */
function FreshnessBanner({ freshness, canBuild }: { freshness: Freshness; canBuild: boolean }) {
  const { t } = useTranslation();
  if (freshness.up_to_date) {
    return freshness.unknown > 0 ? (
      <Alert color="gray" title={t('context.freshness.unknownTitle')}>
        {t('context.freshness.unknown', { count: freshness.unknown })}
      </Alert>
    ) : null;
  }
  const parts = (['changed', 'added', 'removed'] as const)
    .filter((key) => freshness[key] > 0)
    .map((key) => t(`context.freshness.${key}`, { count: freshness[key] }));
  if (freshness.stale_site) {
    parts.push(t('context.freshness.staleSite'));
  }
  const examples = (['changed', 'added', 'removed'] as const).flatMap((key) =>
    freshness.examples[key].map((path) => ({ key, path })),
  );
  return (
    <Alert color="orange" title={t('context.freshness.title')} role="status">
      <Text size="sm">{parts.join(' · ')}</Text>
      {examples.length > 0 && (
        <Text component="details" size="xs" mt={4}>
          <summary style={{ cursor: 'pointer' }}>{t('context.freshness.examples')}</summary>
          <Stack gap={0} mt={2}>
            {examples.map(({ key, path }) => (
              <Text key={`${key}:${path}`} size="xs" ff="monospace">
                {t(`context.freshness.kinds.${key}`)}: {path}
              </Text>
            ))}
          </Stack>
        </Text>
      )}
      <Text size="xs" c="dimmed" mt={4}>
        {t('context.freshness.checkedAt', { date: formatDateTime(freshness.checked_at) })}
      </Text>
      {canBuild && (
        <Button
          mt="xs"
          size="xs"
          variant="light"
          onClick={() => document.getElementById(BUILD_CARD_ID)?.scrollIntoView({ behavior: 'smooth' })}
        >
          {t('context.freshness.rebuild')}
        </Button>
      )}
    </Alert>
  );
}

function BuildCard({
  project,
  context,
  selection,
  onSelectionChange,
  manifestDirty,
  onUseTemplate,
  copyError,
}: {
  project: ProjectOut;
  context: ContextOut | null;
  selection: Selection;
  onSelectionChange: (selection: Selection) => void;
  /** Hay un borrador del manifiesto distinto del guardado: con su catálogo no se construye (A3). */
  manifestDirty: boolean;
  onUseTemplate: (name: string) => void;
  copyError: unknown;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const enqueue = useEnqueueRun(project.id);
  const templates = useTemplates();
  const { catalog, template } = selection;
  const setCatalog = (value: Catalog) => onSelectionChange({ catalog: value, template });
  const setTemplate = (value: string | null) => onSelectionChange({ catalog, template: value });
  const [domains, setDomains] = useState<string[]>([]);
  const [folder, setFolder] = useState('organizado');
  const [threshold, setThreshold] = useState(0.5);
  const [buildSite, setBuildSite] = useState(true);
  const status = useAiStatus();
  const [withAi, setWithAi] = useState(false);
  const [withEnrichment, setWithEnrichment] = useState(false);
  const aiAvailable = status.data?.[aiTask(catalog)] === true;
  const enrichmentAvailable = status.data?.enrich === true;

  const blockedByDraft = catalog === 'manifest' && manifestDirty;
  const ready =
    (catalog !== 'domains' || domains.length > 0) &&
    (catalog !== 'template' || template !== null) &&
    !blockedByDraft;
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
        ai_enrichment: withEnrichment && enrichmentAvailable,
      }),
      { onSuccess: (run) => void navigate(`/runs/${run.id}`) },
    );

  return (
    <Card withBorder id={BUILD_CARD_ID}>
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
        {catalog === 'template' && template !== null && (
          <Group gap="xs">
            <Button variant="default" size="xs" onClick={() => onUseTemplate(template)}>
              {t('context.build.useTemplateAsManifest')}
            </Button>
            <Text size="xs" c="dimmed">
              {t('context.build.useTemplateAsManifestHint')}
            </Text>
          </Group>
        )}
        {copyError !== null && <ErrorAlert error={copyError} />}
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
            aiAvailable ? 'context.ai.classifyHelp' : `context.ai.notConfigured.${aiTask(catalog)}`,
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
        <Switch
          label={t('context.ai.enrich')}
          description={t(enrichmentAvailable ? 'context.ai.enrichHelp' : 'context.ai.notConfigured.enrich')}
          checked={withEnrichment && enrichmentAvailable}
          disabled={!enrichmentAvailable}
          onChange={(event) => setWithEnrichment(event.currentTarget.checked)}
        />
        {withEnrichment && enrichmentAvailable && (
          <Alert color="grape" title={t('context.ai.egressTitle')}>
            {t('context.ai.enrichEgress')}
          </Alert>
        )}
        {blockedByDraft && (
          <Alert color="orange" role="status">
            {t('context.build.unsavedManifest')}
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
  const [language, setLanguage] = useState('');
  const [keyword, setKeyword] = useState('');
  const [axisFilters, setAxisFilters] = useState<string[]>([]);
  const [debouncedLanguage] = useDebouncedValue(language.trim().toLowerCase(), 300);
  const [debouncedKeyword] = useDebouncedValue(keyword, 300);
  const list = useListState(CONTEXT_DOCUMENT_SORT, 'doc');
  const documents = useContextDocuments(
    projectId,
    domain,
    {
      only,
      // La API pide entre 2 y 8 caracteres: con uno solo, todavía no se filtra.
      language: debouncedLanguage.length >= 2 ? debouncedLanguage : null,
      keyword: debouncedKeyword,
      axis: axisFilters,
    },
    list.query,
  );
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
            { value: 'ai_disagrees', label: t('context.documents.aiDisagrees') },
          ]}
        />
      </Group>
      <Group align="flex-end" gap="sm">
        <div style={{ flex: 1, minWidth: 200 }}>
          <SearchBox value={list.q} onChange={list.setQ} label={t('context.documents.search')} />
        </div>
        <TextInput
          label={t('context.documents.language')}
          placeholder="es"
          value={language}
          maxLength={8}
          w={110}
          onChange={(event) => {
            setLanguage(event.currentTarget.value);
            list.paging.setPage(1, true);
          }}
        />
        <TextInput
          label={t('context.documents.keyword')}
          value={keyword}
          maxLength={100}
          w={200}
          onChange={(event) => {
            setKeyword(event.currentTarget.value);
            list.paging.setPage(1, true);
          }}
        />
      </Group>
      <AxisFilters
        axes={context.taxonomy_axes ?? []}
        value={axisFilters}
        onChange={(value) => {
          setAxisFilters(value);
          list.paging.setPage(1, true);
        }}
      />
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
          {domain === null && documents.data.items.some((doc) => !doc.unclassified_reason) && (
            <Text size="xs" c="dimmed">
              {t('context.unclassified.rebuild')}
            </Text>
          )}
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
                  {domain === null ? (
                    // Los sin clasificar no se copian: en su lugar, por qué no se clasificaron (1.6.0, G42).
                    <Table.Th>{t('context.unclassified.reason')}</Table.Th>
                  ) : (
                    <SortableTh state={list} sortKey="organized_path">
                      {t('context.documents.copy')}
                    </SortableTh>
                  )}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {documents.data.items.map((doc) => {
                  const original = doc.folder ? `${doc.folder}/${doc.path}` : doc.path;
                  return (
                    <Table.Tr key={original}>
                      <Table.Td>
                        <Text size="sm">{doc.title}</Text>
                        <DocumentProperties doc={doc} />
                        <AxisBadges axes={context.taxonomy_axes ?? []} values={doc.axes ?? {}} />
                        <HowClassified doc={doc} context={context} />
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
                        {domain === null ? (
                          doc.unclassified_reason ? (
                            <Badge
                              variant="light"
                              color={doc.unclassified_reason === 'incomplete_artifacts' ? 'red' : 'gray'}
                              title={t(`context.unclassified.${doc.unclassified_reason}Help`)}
                            >
                              {t(`context.unclassified.${doc.unclassified_reason}`)}
                            </Badge>
                          ) : (
                            '—'
                          )
                        ) : doc.failed ? (
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

const percent = (value: number) => `${Math.round(value * 100)} %`;

/**
 * Autor, idioma, palabras clave y descripción del documento (1.5.0). Lo que rellenó la IA porque el documento no lo
 * declaraba lleva la marca «IA».
 */
function DocumentProperties({ doc }: { doc: ContextDocument }) {
  const { t } = useTranslation();
  const byAi = (field: string) =>
    doc.ai_filled.includes(field) ? (
      <Badge ml={4} size="xs" variant="light" color="grape" title={t('context.properties.byAi')}>
        {t('context.ai.badge')}
      </Badge>
    ) : null;
  const meta = [
    doc.author && t('context.properties.author', { author: doc.author }),
    doc.language && t('context.properties.language', { language: doc.language }),
  ].filter(Boolean);
  if (meta.length === 0 && doc.keywords.length === 0 && !doc.description) {
    return null;
  }
  return (
    <Stack gap={2} mt={2}>
      {meta.length > 0 && (
        <Text size="xs" c="dimmed">
          {meta.join(' · ')}
        </Text>
      )}
      {doc.description && (
        <Text size="xs">
          {doc.description}
          {byAi('description')}
        </Text>
      )}
      {doc.keywords.length > 0 && (
        <Group gap={4}>
          {doc.keywords.map((keyword) => (
            <Badge key={keyword} size="xs" variant="outline" color="gray" tt="none">
              {keyword}
            </Badge>
          ))}
          {byAi('keywords')}
        </Group>
      )}
    </Stack>
  );
}

/** Detalle plegable «Cómo se clasificó» (1.5.0): reglas, propuesta de la IA y su justificación. */
function HowClassified({ doc, context }: { doc: ContextDocument; context: ContextOut }) {
  const { t } = useTranslation();
  const materialConfidence = doc.material_type_confidence;
  const evidence = Object.values(doc.axes ?? {}).some((items) =>
    items.some((item) => item.evidence || item.classified_by === 'ai'),
  );
  if (!doc.rules_domain && !doc.ai_domain && typeof materialConfidence !== 'number' && !evidence) {
    return null;
  }
  return (
    <Text component="details" size="xs" mt={2}>
      <summary style={{ cursor: 'pointer' }}>{t('context.how.title')}</summary>
      <Stack gap={2} mt={2}>
        {doc.rules_domain && (
          <Text size="xs">
            {t('context.how.rules', {
              domain: doc.rules_domain,
              confidence: percent(doc.rules_confidence ?? 0),
            })}
          </Text>
        )}
        {doc.ai_domain && (
          <Text size="xs">
            {t('context.how.ai', { domain: doc.ai_domain, confidence: percent(doc.ai_confidence ?? 0) })}
            {doc.ai_domain !== doc.domain_slug && (
              <Badge ml={4} size="xs" variant="light" color="orange">
                {t('context.how.notApplied')}
              </Badge>
            )}
          </Text>
        )}
        {doc.ai_reasoning && (
          <Text size="xs" c="dimmed">
            {t('context.how.reasoning', { reasoning: doc.ai_reasoning })}
          </Text>
        )}
        {typeof materialConfidence === 'number' && (
          <Text size="xs">{t('context.how.material', { confidence: percent(materialConfidence) })}</Text>
        )}
        <AxisEvidence
          axes={context.taxonomy_axes ?? []}
          values={doc.axes ?? {}}
          provenance={context.ai_provenance ?? []}
        />
      </Stack>
    </Text>
  );
}

/**
 * Historial del contexto (1.5.0): las últimas construcciones (fecha, versión, modelos y recuentos) y, al desplegar
 * una, los documentos que entraron, salieron o cambiaron de sitio. Se conserva al borrar el contexto.
 */
function HistoryCard({ projectId }: { projectId: number }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const history = useContextHistory(projectId);
  const enqueue = useEnqueueRun(projectId);
  const exportButton = (
    <Button
      variant="light"
      size="xs"
      loading={enqueue.isPending}
      onClick={() =>
        enqueue.mutate(CONTEXT_HISTORY_XLSX, { onSuccess: (run) => void navigate(`/runs/${run.id}`) })
      }
    >
      {t('context.history.export')}
    </Button>
  );

  return (
    <Card withBorder component="section" aria-label={t('context.history.title')}>
      <Group justify="space-between" mb="xs">
        <Title order={3} size="h4">
          {t('context.history.title')}
        </Title>
        {history.data && (history.data.total > 0 || history.data.error) && exportButton}
      </Group>
      <Text size="sm" c="dimmed" mb="xs">
        {t('context.history.intro')}
      </Text>
      {enqueue.isError && <ErrorAlert error={enqueue.error} mb="xs" />}
      {history.isError ? (
        <ErrorAlert error={history.error} />
      ) : !history.data ? (
        <Loader size="sm" aria-label={t('common.loading')} />
      ) : history.data.error ? (
        <Alert color="orange">{t('context.history.tooLarge')}</Alert>
      ) : history.data.items.length === 0 ? (
        <Text c="dimmed" role="status">
          {t('context.history.empty')}
        </Text>
      ) : (
        <Stack gap="xs">
          {history.data.items.map((build) => (
            <BuildEntry key={build.built_at} build={build} />
          ))}
          {history.data.total > history.data.items.length && (
            <Text size="xs" c="dimmed">
              {t('context.history.older', { count: history.data.total - history.data.items.length })}
            </Text>
          )}
        </Stack>
      )}
    </Card>
  );
}

function BuildEntry({ build }: { build: ContextBuild }) {
  const { t } = useTranslation();
  const none = t('context.history.none');
  const trace = [
    build.built_with_version && t('context.trace.version', { version: build.built_with_version }),
    build.ai_classification_model &&
      t('context.trace.classificationModel', { model: build.ai_classification_model }),
    build.ai_enrichment_model && t('context.trace.enrichmentModel', { model: build.ai_enrichment_model }),
  ].filter(Boolean);
  return (
    <Text component="details" size="sm">
      <summary style={{ cursor: 'pointer' }}>
        {t('context.history.build', {
          date: formatDateTime(build.built_at),
          classified: formatCount(build.classified),
          unclassified: formatCount(build.unclassified),
        })}{' '}
        <Badge size="xs" variant="light" color={build.changes_total ? 'blue' : 'gray'}>
          {build.changes_total
            ? t('context.history.changes', { count: build.changes_total })
            : t('context.history.noChanges')}
        </Badge>
      </summary>
      {trace.length > 0 && (
        <Text size="xs" c="dimmed" mt={4}>
          {trace.join(' · ')}
        </Text>
      )}
      {build.changes.length > 0 && (
        <Table.ScrollContainer minWidth={480} mt="xs">
          <Table>
            <Table.Tbody>
              {build.changes.map((change) => (
                <Table.Tr key={`${change.change}:${change.path}`}>
                  <Table.Td w={80}>
                    <Badge size="xs" variant="light">
                      {t(`context.history.kinds.${change.change}`)}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text ff="monospace" size="xs" style={{ wordBreak: 'break-all' }}>
                      {change.path}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs">
                      {change.change === 'added'
                        ? (change.domain ?? none)
                        : `${change.previous_domain ?? none} → ${change.domain ?? none}`}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {build.changes_total > build.changes.length && (
        <Text size="xs" c="dimmed" mt={4}>
          {t('context.history.shown', { shown: build.changes.length, total: build.changes_total })}
        </Text>
      )}
    </Text>
  );
}
