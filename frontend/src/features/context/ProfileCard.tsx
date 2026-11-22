import { Alert, Badge, Button, Card, Code, Group, Stack, Text, Textarea, Title } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { ErrorAlert } from '../../components/ErrorAlert';
import { useAiStatus } from '../admin/useAi';
import { profileMode, type Selection } from './useContext';

type Profile = components['schemas']['ProjectProfileOut'];
type Preview = components['schemas']['PromptPreviewOut'];
type Sections = components['schemas']['ProfileSectionsOut'];

/** Tamaño máximo de `profile.md` (`MAX_PROFILE_BYTES` de la API). */
const MAX_PROFILE_BYTES = 32 * 1024;
const PLACEHOLDER = `## Contexto del proyecto
…

## Reglas de desempate
- …

## Glosario
- …

## Ejemplos
- «Título de un documento» → dominio, tipo`;

const profileKey = (projectId: number) => ['projects', projectId, 'context', 'profile'] as const;

function useProfile(projectId: number) {
  return useQuery({
    queryKey: profileKey(projectId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}/context/profile', {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
}

function useProfileChange(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ markdown, etag }: { markdown: string | null; etag: string }) => {
      const params = { path: { project_id: projectId }, header: { 'if-match': etag } };
      return markdown === null
        ? unwrap(await api.DELETE('/api/v1/projects/{project_id}/context/profile', { params }))
        : unwrap(
            await api.PUT('/api/v1/projects/{project_id}/context/profile', { params, body: { markdown } }),
          );
    },
    onSuccess: (saved) => queryClient.setQueryData(profileKey(projectId), saved),
  });
}

function usePromptPreview(projectId: number) {
  return useMutation({
    mutationFn: async (body: components['schemas']['PromptPreviewIn']) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/context/prompt-preview', {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
  });
}

/**
 * Perfil propio del proyecto (`.doc_organize/profile.md`, D11): se añade al de la plantilla o el manifiesto y va en el
 * prompt de clasificar y describir con IA. Con «Vista previa del prompt» se ve lo que recibiría el modelo, sin llamarlo.
 *
 * Se muestra según el catálogo (`profileMode`, D1 de 2026-11-22): completo con plantilla; con carpetas o lista de
 * dominios, si hay IA configurada o ya existe; con el manifiesto, solo un aviso si existe, con «Copiar al cuerpo del
 * manifiesto». Con cambios sin guardar se sigue mostrando completo aunque cambie el catálogo.
 */
export function ProfileCard({
  projectId,
  editable,
  selection,
  onDirtyChange,
  onCopyToManifest,
}: {
  projectId: number;
  editable: boolean;
  selection: Selection;
  /** Avisa a la página de si hay cambios sin guardar (aviso al salir). */
  onDirtyChange?: (dirty: boolean) => void;
  /** Copia el perfil al final del borrador del manifiesto (sin guardar); `undefined` si no se puede editar. */
  onCopyToManifest?: ((markdown: string) => void) | undefined;
}) {
  const { t } = useTranslation();
  const profile = useProfile(projectId);
  const change = useProfileChange(projectId);
  const preview = usePromptPreview(projectId);
  const status = useAiStatus();
  const [draft, setDraft] = useState<string | null>(null);
  const [notice, setNotice] = useState<'saved' | 'deleted' | null>(null);
  const [expanded, setExpanded] = useState(false);

  const saved: Profile | undefined = profile.data;
  const text = draft ?? saved?.markdown ?? '';
  const dirty = draft !== null && draft !== (saved?.markdown ?? '');

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  if (profile.isError) {
    return <ErrorAlert error={profile.error} />;
  }
  if (profile.isPending && selection.catalog !== 'template') {
    return null;
  }
  const aiConfigured = status.data?.classify === true || status.data?.enrich === true;
  const mode = dirty ? 'full' : profileMode(selection.catalog, aiConfigured, Boolean(saved?.markdown));
  if (mode === 'hidden') {
    return null;
  }
  if (mode === 'manifestNotice' && !expanded) {
    return (
      <section aria-label={t('context.profile.title')}>
        <Alert color="blue" title={t('context.profile.manifestNotice.title')}>
          <Text size="sm">{t('context.profile.manifestNotice.body')}</Text>
          <Group mt="xs" gap="xs">
            <Button size="xs" variant="default" onClick={() => setExpanded(true)}>
              {t('context.profile.manifestNotice.view')}
            </Button>
            {editable && onCopyToManifest && saved?.markdown && (
              <Button size="xs" variant="light" onClick={() => onCopyToManifest(saved.markdown ?? '')}>
                {t('context.profile.manifestNotice.copy')}
              </Button>
            )}
          </Group>
        </Alert>
      </section>
    );
  }
  const tooLarge = new TextEncoder().encode(text).length > MAX_PROFILE_BYTES;
  const previewable =
    selection.catalog === 'manifest' || (selection.catalog === 'template' && !!selection.template);
  const aiOnly = selection.catalog === 'discover' || selection.catalog === 'domains';

  return (
    <Card withBorder component="section" aria-label={t('context.profile.title')}>
      <Title order={3} size="h4" mb="xs">
        {t('context.profile.title')}
      </Title>
      <Text size="sm" c="dimmed" mb="xs">
        {t('context.profile.intro')}
      </Text>
      {aiOnly && (
        <Text size="xs" c="dimmed" mb="xs">
          {t('context.profile.aiOnly')}
        </Text>
      )}
      {mode === 'manifestNotice' && (
        <Alert color="blue" mb="xs">
          <Text size="sm">{t('context.profile.manifestNotice.body')}</Text>
          {editable && onCopyToManifest && saved?.markdown && (
            <Button mt="xs" size="xs" variant="light" onClick={() => onCopyToManifest(saved.markdown ?? '')}>
              {t('context.profile.manifestNotice.copy')}
            </Button>
          )}
        </Alert>
      )}
      {saved?.markdown && !saved.sections && (
        <Alert color="orange" mb="xs">
          {t('context.profile.noSections')}
        </Alert>
      )}
      <Textarea
        label={t('context.profile.markdown')}
        value={text}
        placeholder={PLACEHOLDER}
        readOnly={!editable}
        onChange={(event) => {
          setDraft(event.currentTarget.value);
          setNotice(null);
        }}
        rows={8}
        resize="vertical"
        styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
        error={tooLarge ? t('context.profile.tooLarge') : undefined}
      />
      {change.isError && <ErrorAlert error={change.error} mt="xs" />}
      {notice && (
        <Text size="sm" c="teal" role="status" mt="xs">
          {t(`context.profile.${notice}`)}
        </Text>
      )}
      <Group justify="space-between" mt="xs">
        <Button
          variant="default"
          disabled={!previewable || tooLarge}
          loading={preview.isPending}
          title={previewable ? undefined : t('context.profile.previewNeedsCatalog')}
          onClick={() =>
            preview.mutate({
              catalog: selection.catalog === 'template' ? 'template' : 'manifest',
              template_name: selection.catalog === 'template' ? selection.template : null,
              profile_markdown: dirty ? text : null,
            })
          }
        >
          {t('context.profile.preview')}
        </Button>
        {editable && (
          <Group>
            {saved?.markdown && (
              <Button
                color="red"
                variant="light"
                loading={change.isPending && change.variables?.markdown === null}
                onClick={() =>
                  change.mutate(
                    { markdown: null, etag: saved.etag },
                    {
                      onSuccess: () => {
                        setDraft(null);
                        setNotice('deleted');
                      },
                    },
                  )
                }
              >
                {t('context.profile.delete')}
              </Button>
            )}
            <Button
              disabled={!dirty || !text.trim() || tooLarge || !saved}
              loading={change.isPending && change.variables?.markdown !== null}
              onClick={() =>
                saved &&
                change.mutate(
                  { markdown: text, etag: saved.etag },
                  {
                    onSuccess: () => {
                      setDraft(null);
                      setNotice('saved');
                    },
                  },
                )
              }
            >
              {t('context.profile.save')}
            </Button>
          </Group>
        )}
      </Group>
      {!previewable && (
        <Text size="xs" c="dimmed" mt={4}>
          {t('context.profile.previewNeedsCatalog')}
        </Text>
      )}
      {preview.isError && <ErrorAlert error={preview.error} mt="xs" />}
      {preview.data && <PromptPreview preview={preview.data} />}
    </Card>
  );
}

/** Mensajes que recibiría el modelo y de dónde sale cada parte del perfil. */
export function PromptPreview({ preview }: { preview: Preview }) {
  const { t } = useTranslation();
  return (
    <Stack gap="xs" mt="sm" aria-label={t('context.profile.previewTitle')} role="region">
      <Text fw={500} size="sm">
        {t('context.profile.previewTitle')}
      </Text>
      <Text size="xs" c="dimmed">
        {t('context.profile.previewHelp')}
      </Text>
      <Group gap={4}>
        <Badge variant="light" color={preview.template_profile ? 'blue' : 'gray'}>
          {t(preview.template_profile ? 'context.profile.fromTemplate' : 'context.profile.noTemplateProfile')}
        </Badge>
        <Badge variant="light" color={preview.project_profile ? 'teal' : 'gray'}>
          {t(preview.project_profile ? 'context.profile.fromProject' : 'context.profile.noProjectProfile')}
        </Badge>
        {preview.profile && <SectionsSummary sections={preview.profile} />}
      </Group>
      {preview.messages.map((message, index) => (
        <div key={index}>
          <Text size="xs" fw={500}>
            {t(`context.profile.roles.${message.role}`, { defaultValue: message.role })}
          </Text>
          <Code block style={{ whiteSpace: 'pre-wrap', maxHeight: 320, overflow: 'auto' }}>
            {message.content}
          </Code>
        </div>
      ))}
    </Stack>
  );
}

function SectionsSummary({ sections }: { sections: Sections }) {
  const { t } = useTranslation();
  return (
    <Text size="xs" c="dimmed">
      {t('context.profile.examples', { count: sections.examples.length })}
    </Text>
  );
}
