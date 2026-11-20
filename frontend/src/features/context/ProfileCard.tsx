import { Alert, Badge, Button, Card, Code, Group, Stack, Text, Textarea, Title } from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { ErrorAlert } from '../../components/ErrorAlert';
import type { Selection } from './useContext';

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
 * prompt de clasificación. Con «Vista previa del prompt» se ve lo que recibiría el modelo, sin llamarlo.
 */
export function ProfileCard({
  projectId,
  editable,
  selection,
}: {
  projectId: number;
  editable: boolean;
  selection: Selection;
}) {
  const { t } = useTranslation();
  const profile = useProfile(projectId);
  const change = useProfileChange(projectId);
  const preview = usePromptPreview(projectId);
  const [draft, setDraft] = useState<string | null>(null);
  const [notice, setNotice] = useState<'saved' | 'deleted' | null>(null);

  if (profile.isError) {
    return <ErrorAlert error={profile.error} />;
  }
  const saved: Profile | undefined = profile.data;
  const text = draft ?? saved?.markdown ?? '';
  const dirty = draft !== null && draft !== (saved?.markdown ?? '');
  const tooLarge = new TextEncoder().encode(text).length > MAX_PROFILE_BYTES;
  const previewable =
    selection.catalog === 'manifest' || (selection.catalog === 'template' && !!selection.template);

  return (
    <Card withBorder component="section" aria-label={t('context.profile.title')}>
      <Title order={3} size="h4" mb="xs">
        {t('context.profile.title')}
      </Title>
      <Text size="sm" c="dimmed" mb="xs">
        {t('context.profile.intro')}
      </Text>
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
