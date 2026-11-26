import {
  Alert,
  Anchor,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { type RefObject, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ConfirmModal } from '../../components/ConfirmModal';
import { ErrorAlert } from '../../components/ErrorAlert';
import { AgentPanel, RulesCheck } from './AgentPanel';
import { FrontMatterNotices } from './Axes';
import { DraftPanel } from './ManifestDraftPanel';
import { ManifestVersions } from './ManifestVersions';
import {
  contextIsStale,
  type ContextOut,
  MAX_TEMPLATE_BYTES,
  sameText,
  useDeleteManifest,
  useManifest,
  useSaveManifest,
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

/** Zona plegable «Crear o mejorar con IA». */
const CREATE_ID = 'manifiesto-crear';

/**
 * Manifiesto de taxonomía del proyecto, en orden de trabajo (2026-11-22): estado → crear o mejorar con IA (borrador o
 * agente) → editor → comprobar y guardar → versiones → borrar.
 */
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
  /** «Crear o mejorar con IA»: abierto sin manifiesto, cerrado con él, salvo que la persona lo cambie. */
  const [createOpen, setCreateOpen] = useState<boolean | null>(null);

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
  const showCreate = createOpen ?? saved.markdown === null;

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
      {saved.markdown !== null && !saved.error && <FrontMatterNotices report={saved.front_matter} />}
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
        // Siempre montado (`hidden`): un borrador o el agente en marcha siguen su ejecución aunque se pliegue.
        <Stack gap={0} mb="xs">
          <Anchor
            component="button"
            type="button"
            size="sm"
            w="fit-content"
            aria-expanded={showCreate}
            aria-controls={CREATE_ID}
            onClick={() => setCreateOpen(!showCreate)}
          >
            {t(showCreate ? 'context.manifest.createHide' : 'context.manifest.createShow')}
          </Anchor>
          <div id={CREATE_ID} hidden={!showCreate}>
            <Text size="xs" c="dimmed" my="xs">
              {t('context.manifest.createHelp')}
            </Text>
            <DraftPanel
              projectId={projectId}
              onDraft={(markdown) => onReplace(markdown, t('context.manifest.replaceBodyDraft'))}
            />
            <AgentPanel
              projectId={projectId}
              hasManifest={saved.markdown !== null && !saved.error}
              onLoad={(markdown) => onReplace(markdown, t('context.agent.replaceBody'))}
            />
          </div>
        </Stack>
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
      {editable && <RulesCheck projectId={projectId} markdown={text} />}
      {save.isError && <ErrorAlert error={save.error} mt="xs" />}
      {remove.isError && <ErrorAlert error={remove.error} mt="xs" />}
      {notice && (
        <Text size="sm" c="teal" role="status" mt="xs">
          {t(`context.manifest.${notice}`)}
        </Text>
      )}
      {editable && (
        <Group justify="flex-end" mt="xs">
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
      {editable && saved.markdown !== null && (
        <Group mt="sm">
          <Button
            color="red"
            variant="light"
            onClick={() => {
              remove.reset();
              setDeleting(true);
            }}
          >
            {t('context.manifest.delete')}
          </Button>
        </Group>
      )}
      <ConfirmModal
        opened={deleting}
        onClose={() => {
          setDeleting(false);
          remove.reset();
        }}
        title={t('context.manifest.deleteTitle')}
        message={t('context.manifest.deleteConfirm')}
        error={remove.error}
        confirmLabel={t('context.manifest.delete')}
        loading={remove.isPending}
        onConfirm={() =>
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
      />
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
