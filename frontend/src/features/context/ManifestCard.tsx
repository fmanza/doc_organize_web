import {
  Accordion,
  Alert,
  Anchor,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Modal,
  NumberInput,
  Stack,
  Table,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { type RefObject, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { useAiStatus } from '../admin/useAi';
import {
  type ContextOut,
  contextIsStale,
  type Manifest,
  type ManifestVersion,
  manifestVersionQuery,
  MAX_TEMPLATE_BYTES,
  useDeleteManifest,
  useManifest,
  useManifestVersions,
  useRestoreManifest,
  useSaveManifest,
  sameText,
  useTaxonomyDraft,
} from './useContext';

export interface ManifestCardProps {
  projectId: number;
  editable: boolean;
  context: ContextOut | null;
  /** Borrador sin guardar (vive en la página: sobrevive a cambiar de catálogo). `null` = el texto guardado. */
  draft: string | null;
  onDraftChange: (markdown: string | null) => void;
  /** Sustituye el borrador pidiendo confirmación si hay otro texto (copia, IA o versión: `replaceDraft`). */
  onReplace: (markdown: string, body: string) => void;
  /** Plantilla de la que se copió el borrador, con «Deshacer». */
  copiedFrom: string | null;
  onUndoCopy: () => void;
  /** Cambia tras copiar una plantilla: lleva el foco al editor (A7). */
  focusToken: number;
}

/** Manifiesto de taxonomía del proyecto: editor, borrador con IA, versiones, restaurar y borrar. */
export function ManifestCard({
  projectId,
  editable,
  context,
  draft,
  onDraftChange,
  onReplace,
  copiedFrom,
  onUndoCopy,
  focusToken,
}: ManifestCardProps) {
  const { t } = useTranslation();
  const manifest = useManifest(projectId);
  const save = useSaveManifest(projectId);
  const remove = useDeleteManifest(projectId);
  const editor = useRef<HTMLTextAreaElement>(null);
  const [deleting, setDeleting] = useState(false);
  const [notice, setNotice] = useState<'saved' | 'deleted' | 'restored' | null>(null);

  useFocus(editor, focusToken, manifest.isSuccess);

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
  const saved = manifest.data;
  const text = draft ?? saved.markdown ?? '';
  const dirty = draft !== null && !sameText(draft, saved.markdown);
  const tooLarge = new TextEncoder().encode(text).length > MAX_TEMPLATE_BYTES;

  const edit = (markdown: string | null) => {
    setNotice(null);
    onDraftChange(markdown);
  };

  return (
    <Card withBorder component="section" aria-label={t('context.manifest.title')}>
      <Title order={3} size="h4" mb="xs">
        {t('context.manifest.title')}
      </Title>
      <Text size="sm" c="dimmed" mb="xs">
        {t('context.manifest.intro')}
      </Text>
      {contextIsStale(context, saved) && (
        <Alert color="orange" mb="xs">
          {t('context.manifest.contextStale')}
        </Alert>
      )}
      {saved.error && (
        <Alert color="orange" mb="xs" title={t('context.manifest.invalid')}>
          {saved.error}
        </Alert>
      )}
      {saved.markdown !== null && !saved.error && (
        <Text size="sm" mb="xs">
          {t('context.manifest.catalog', {
            domains: saved.domains.length,
            materials: saved.material_types.length,
          })}
        </Text>
      )}
      {copiedFrom !== null && (
        <Alert color="blue" mb="xs" role="status">
          <Group justify="space-between" wrap="nowrap">
            <Text size="sm">{t('context.manifest.copied', { name: copiedFrom })}</Text>
            <Button size="xs" variant="subtle" onClick={onUndoCopy}>
              {t('context.manifest.undoCopy')}
            </Button>
          </Group>
        </Alert>
      )}
      {editable && (
        <DraftPanel
          projectId={projectId}
          onDraft={(markdown) => onReplace(markdown, t('context.manifest.replaceBodyDraft'))}
        />
      )}
      <Textarea
        ref={editor}
        label={t('context.manifest.markdown')}
        value={text}
        onChange={(event) => edit(event.currentTarget.value)}
        readOnly={!editable}
        rows={10}
        resize="vertical"
        styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
        error={tooLarge ? t('context.manifest.tooLarge') : undefined}
      />
      {save.isError && <ErrorAlert error={save.error} mt="xs" />}
      {remove.isError && <ErrorAlert error={remove.error} mt="xs" />}
      {notice && (
        <Text size="sm" c="teal" role="status" mt="xs">
          {t(`context.manifest.${notice}`)}
        </Text>
      )}
      {editable && (
        <Group justify="space-between" mt="xs">
          <Group>
            {saved.markdown !== null && (
              <Button color="red" variant="light" onClick={() => setDeleting(true)}>
                {t('context.manifest.delete')}
              </Button>
            )}
          </Group>
          <Button
            onClick={() =>
              save.mutate(
                { markdown: text, etag: saved.etag },
                {
                  onSuccess: () => {
                    onDraftChange(null);
                    setNotice('saved');
                  },
                },
              )
            }
            loading={save.isPending}
            disabled={!dirty || !text.trim() || tooLarge}
          >
            {t('context.manifest.save')}
          </Button>
        </Group>
      )}
      <ManifestVersions
        projectId={projectId}
        editable={editable}
        manifest={saved}
        dirty={dirty}
        onRestored={() => {
          onDraftChange(null);
          setNotice('restored');
        }}
        onLoad={(markdown, date) => onReplace(markdown, t('context.manifest.replaceBodyVersion', { date }))}
      />
      <Modal opened={deleting} onClose={() => setDeleting(false)} title={t('context.manifest.deleteTitle')}>
        <Stack>
          <Text>{t('context.manifest.deleteConfirm')}</Text>
          {remove.isError && <ErrorAlert error={remove.error} />}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleting(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              color="red"
              loading={remove.isPending}
              onClick={() =>
                remove.mutate(
                  { etag: saved.etag },
                  {
                    onSuccess: () => {
                      setDeleting(false);
                      onDraftChange(null);
                      setNotice('deleted');
                    },
                  },
                )
              }
            >
              {t('context.manifest.delete')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Card>
  );
}

/** Lleva el foco al editor cuando cambia `token` (tras copiar una plantilla el botón pulsado desaparece). */
function useFocus(ref: RefObject<HTMLTextAreaElement | null>, token: number, ready: boolean) {
  useEffect(() => {
    if (token > 0 && ready) {
      ref.current?.focus();
    }
  }, [ref, token, ready]);
}

function VersionCatalog({ version }: { version: ManifestVersion }) {
  const { t } = useTranslation();
  if (version.empty) {
    return t('context.manifest.versionEmpty');
  }
  if (!version.valid) {
    return t('context.manifest.versionInvalid');
  }
  return t('context.manifest.versionCounts', { domains: version.domains, materials: version.material_types });
}

/** Versiones anteriores: «Restaurar la versión anterior», lista con «Ver» y «Restaurar» o «Cargar en el editor». */
function ManifestVersions({
  projectId,
  editable,
  manifest,
  dirty,
  onRestored,
  onLoad,
}: {
  projectId: number;
  editable: boolean;
  manifest: Manifest;
  dirty: boolean;
  onRestored: () => void;
  onLoad: (markdown: string, date: string) => void;
}) {
  const { t } = useTranslation();
  const versions = useManifestVersions(projectId);
  const restore = useRestoreManifest(projectId);
  const [restoring, setRestoring] = useState<ManifestVersion | null>(null);
  const [viewing, setViewing] = useState<ManifestVersion | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const queryClient = useQueryClient();
  const detail = useQuery({
    ...manifestVersionQuery(projectId, viewing?.id ?? 0),
    enabled: viewing !== null,
  });

  /** «Cargar en el editor» (versión no válida): se pide el texto al pulsar y pasa por la confirmación común. */
  const load = (version: ManifestVersion) => {
    setLoadError(null);
    queryClient
      .fetchQuery(manifestVersionQuery(projectId, version.id))
      .then((found) => {
        if (found.markdown !== null) {
          onLoad(found.markdown, formatDateTime(found.created_at));
        }
      })
      .catch(setLoadError);
  };

  if (versions.isPending) {
    return null;
  }
  if (versions.isError) {
    return <ErrorAlert error={versions.error} mt="xs" />;
  }
  const items = versions.data.items;
  const latest = items[0];
  const restorable = (version: ManifestVersion) => version.valid || version.empty;
  const actionLabel = (version: ManifestVersion) => t(`context.manifest.versionAction.${version.action}`);

  return (
    <Stack gap="xs" mt="sm">
      {editable && latest && restorable(latest) && (
        <Group>
          <Button variant="default" onClick={() => setRestoring(latest)}>
            {t('context.manifest.restorePrevious')}
          </Button>
        </Group>
      )}
      <Accordion variant="contained">
        <Accordion.Item value="versions">
          <Accordion.Control>{t('context.manifest.versions', { count: items.length })}</Accordion.Control>
          <Accordion.Panel>
            <Text size="xs" c="dimmed" mb="xs">
              {t('context.manifest.versionsHint', { limit: versions.data.limit })}
            </Text>
            {items.length === 0 ? (
              <Text size="sm" c="dimmed">
                {t('context.manifest.versionsEmpty')}
              </Text>
            ) : (
              <Table.ScrollContainer minWidth={520}>
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{t('context.manifest.versionDate')}</Table.Th>
                      <Table.Th>{t('context.manifest.versionUser')}</Table.Th>
                      <Table.Th>{t('context.manifest.versionChange')}</Table.Th>
                      <Table.Th>{t('context.manifest.versionCatalog')}</Table.Th>
                      <Table.Th />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {items.map((version) => (
                      <Table.Tr key={version.id}>
                        <Table.Td>{formatDateTime(version.created_at)}</Table.Td>
                        <Table.Td>{version.created_by ?? t('context.manifest.unknownUser')}</Table.Td>
                        <Table.Td>{actionLabel(version)}</Table.Td>
                        <Table.Td>
                          <VersionCatalog version={version} />
                        </Table.Td>
                        <Table.Td>
                          <Group gap="xs" wrap="nowrap">
                            {!version.empty && (
                              <Anchor component="button" size="sm" onClick={() => setViewing(version)}>
                                {t('context.manifest.view')}
                              </Anchor>
                            )}
                            {editable && restorable(version) && (
                              <Anchor component="button" size="sm" onClick={() => setRestoring(version)}>
                                {t('context.manifest.restore')}
                              </Anchor>
                            )}
                            {editable && !restorable(version) && (
                              <Anchor component="button" size="sm" onClick={() => load(version)}>
                                {t('context.manifest.loadIntoEditor')}
                              </Anchor>
                            )}
                          </Group>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            )}
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
      {loadError !== null && <ErrorAlert error={loadError} />}

      <Modal
        opened={restoring !== null}
        onClose={() => {
          restore.reset();
          setRestoring(null);
        }}
        title={t('context.manifest.restoreTitle')}
      >
        {restoring && (
          <Stack>
            <Text>
              {t('context.manifest.restoreConfirm', {
                date: formatDateTime(restoring.created_at),
                action: actionLabel(restoring),
                user: restoring.created_by ?? t('context.manifest.unknownUser'),
              })}
            </Text>
            {restoring.empty && <Text size="sm">{t('context.manifest.restoreEmpty')}</Text>}
            {dirty && (
              <Text size="sm" c="orange">
                {t('context.manifest.restoreLosesDraft')}
              </Text>
            )}
            {restore.isError && <ErrorAlert error={restore.error} />}
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setRestoring(null)}>
                {t('common.cancel')}
              </Button>
              <Button
                loading={restore.isPending}
                onClick={() =>
                  restore.mutate(
                    { versionId: restoring.id, etag: manifest.etag },
                    {
                      onSuccess: () => {
                        setRestoring(null);
                        onRestored();
                      },
                    },
                  )
                }
              >
                {t('context.manifest.restore')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      <Modal
        opened={viewing !== null}
        onClose={() => setViewing(null)}
        size="xl"
        title={viewing ? t('context.manifest.viewTitle', { date: formatDateTime(viewing.created_at) }) : ''}
      >
        {detail.isPending ? (
          <Center>
            <Loader aria-label={t('common.loading')} />
          </Center>
        ) : detail.isError ? (
          <ErrorAlert error={detail.error} />
        ) : (
          <Textarea
            aria-label={t('context.manifest.markdown')}
            value={detail.data.markdown ?? ''}
            readOnly
            rows={16}
            styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
          />
        )}
      </Modal>
    </Stack>
  );
}

/**
 * Borrador del manifiesto con IA: lanza el run `taxonomy_draft`, espera a que termine y entrega el Markdown a
 * `onDraft` **sin guardarlo** (la página pide confirmación si sustituye otro texto).
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
