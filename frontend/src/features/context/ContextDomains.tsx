import {
  Anchor,
  Badge,
  Card,
  Center,
  Group,
  Loader,
  SegmentedControl,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { formatCount } from '../../components/format';
import { SearchBox, SortableTh } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { AxisBadges, AxisEvidence, AxisFilters } from './Axes';
import {
  type ContextDocument,
  type ContextDocumentSort,
  type ContextOut,
  type DocumentFilter,
  useContextDocuments,
} from './useContext';

/**
 * Contexto del proyecto (sustituye a `context.html.j2`), en pasos de trabajo (2026-11-22) con `?paso=`:
 * 1 Taxonomía (catálogo, plantilla o manifiesto y perfil) → 2 Construir → 3 Resultado (resumen, dominios, documentos y
 * versiones) → 4 Revisar y 5 Calidad (rutas propias) → 6 Entregar → Historial. Los pasos siguen montados al cambiar de
 * uno a otro (`hidden`), así que el borrador del manifiesto, la selección y las ejecuciones seguidas no se pierden.
 */
const CONTEXT_DOCUMENT_SORT: readonly ContextDocumentSort[] = [
  'title',
  'path',
  'document_type',
  'organized_path',
];

/** Fila del dominio que se está viendo. */
const SELECTED = { bg: 'var(--mantine-color-default-hover)' } as const;

export function Domains({ context, projectId }: { context: ContextOut; projectId: number }) {
  const { t } = useTranslation();
  const [domain, setDomain] = useState<string | null>(context.domains[0]?.slug ?? null);
  const [only, setOnly] = useState<DocumentFilter | null>(null);
  const [language, setLanguage] = useState('');
  const [keyword, setKeyword] = useState('');
  const [axisFilters, setAxisFilters] = useState<string[]>([]);
  const [onlyCurrent, setOnlyCurrent] = useState(false);
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
      current: onlyCurrent,
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
      {(context.version_groups ?? []).length > 0 && (
        <Switch
          mt="xs"
          label={t('context.versions.onlyCurrent')}
          checked={onlyCurrent}
          onChange={(event) => {
            setOnlyCurrent(event.currentTarget.checked);
            list.paging.setPage(1, true);
          }}
        />
      )}
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
                        <Text size="sm">
                          {doc.title}
                          {doc.is_current === false && (
                            <Badge
                              ml={6}
                              size="xs"
                              variant="light"
                              color="gray"
                              title={t('context.versions.oldTitle')}
                            >
                              {t('context.versions.old')}
                              {doc.version && ` · v${doc.version}`}
                            </Badge>
                          )}
                        </Text>
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
