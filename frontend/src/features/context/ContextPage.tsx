import { Alert, Anchor, Button, Center, Group, Loader, Stack, Text } from '@mantine/core';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams, useSearchParams } from 'react-router';
import { ConfirmModal } from '../../components/ConfirmModal';
import { ErrorAlert } from '../../components/ErrorAlert';
import { DangerousOperationModal } from '../projects/DangerousOperationModal';
import { canDo, useProject } from '../projects/useProjects';
import { BuildCard } from './BuildCard';
import { Domains } from './ContextDomains';
import { HistoryCard } from './ContextHistory';
import { ContextNav } from './ContextNav';
import { SiteCard, Summary } from './ContextSummary';
import { DeliveryCard } from './DeliveryCard';
import { ManifestCard } from './ManifestCard';
import { TaxonomyStep } from './TaxonomyStep';
import { UnsavedDraftGuard } from './UnsavedDraft';
import { VersionsCard } from './Versions';
import {
  appendProfile,
  type ContextStep,
  initialSelection,
  type Manifest,
  manifestKey,
  manifestQuery,
  resolveStep,
  sameText,
  type Selection,
  selectionNotReady,
  stepHref,
  templateQuery,
  useContextLeftover,
  useProjectContext,
} from './useContext';

/** Copia de una plantilla al borrador del manifiesto, con lo que había antes para «Deshacer». */
interface Copied {
  name: string;
  previous: { draft: string | null; selection: Selection };
}

export function ContextPage() {
  const { t } = useTranslation();
  const projectId = Number(useParams().projectId);
  const [searchParams] = useSearchParams();
  const project = useProject(projectId);
  const context = useProjectContext(projectId);
  const leftover = useContextLeftover(projectId, context.isSuccess && context.data === null);
  const queryClient = useQueryClient();
  const [deleting, setDeleting] = useState(false);
  // Selección derivada de `built_at` sin efectos (A4): al terminar una construcción vuelve a la del contexto nuevo.
  const [chosen, setChosen] = useState<Selection & { builtAt: string | null }>({
    builtAt: null,
    ...initialSelection(null),
  });
  const [domains, setDomains] = useState<string[]>([]);
  const [draft, setDraft] = useState<string | null>(null);
  const [copied, setCopied] = useState<Copied | null>(null);
  const [confirm, setConfirm] = useState<{ body: string; apply: () => void } | null>(null);
  const [focusToken, setFocusToken] = useState(0);
  const [showManifest, setShowManifest] = useState(false);
  const [copyError, setCopyError] = useState<unknown>(null);
  const [profileDirty, setProfileDirty] = useState(false);
  const onProfileDirty = useCallback((dirty: boolean) => setProfileDirty(dirty), []);

  const savedManifest = queryClient.getQueryData<Manifest>(manifestKey(projectId))?.markdown ?? null;
  const manifestDirty = draft !== null && !sameText(draft, savedManifest);

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
  const step = resolveStep(searchParams.get('paso'), built !== null, canBuild);
  const notReady = selectionNotReady(selection, domains, manifestDirty);

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

  /**
   * «Copiar al cuerpo del manifiesto» (D1): añade el perfil al final del borrador, sin guardar ni borrar nada. El texto
   * guardado se lee al pulsar: `getQueryData` no vuelve a pintar la página cuando llega el manifiesto.
   */
  const copyProfileToManifest = canBuild
    ? (profile: string) => {
        const current = draft ?? queryClient.getQueryData<Manifest>(manifestKey(projectId))?.markdown ?? '';
        setDraft(current.trim() ? appendProfile(current, profile) : `${profile.trim()}\n`);
        setFocusToken((token) => token + 1);
      }
    : undefined;

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
  const readOnlyManifest =
    built?.catalog_kind === 'manifest' || showManifest ? (
      manifestCard(false)
    ) : (
      <Anchor component="button" onClick={() => setShowManifest(true)} w="fit-content">
        {t('context.manifest.show')}
      </Anchor>
    );
  const panel = (name: ContextStep) => ({ hidden: step !== name, 'data-step': name });
  const leftoverFolder = built ? null : (leftover.data ?? null);

  return (
    <Stack>
      <ContextNav projectId={projectId} active={step} />
      <Text c="dimmed">{t('context.intro')}</Text>
      {canDo(project.data, 'editor') && !writable && <Alert color="gray">{t('context.readOnly')}</Alert>}
      {leftoverFolder && (
        <Alert color="orange" title={t('context.leftover.title')} role="status">
          <Text size="sm">{t('context.leftover.body', { folder: leftoverFolder })}</Text>
          <Group mt="xs" gap="xs">
            {canBuild && (
              <Button component={Link} to={stepHref(projectId, 'construir')} size="xs" variant="light">
                {t('context.leftover.build')}
              </Button>
            )}
            {canDo(project.data, 'owner') && writable && (
              <Button size="xs" color="red" variant="light" onClick={() => setDeleting(true)}>
                {t('projects.danger.context_delete.button')}
              </Button>
            )}
          </Group>
        </Alert>
      )}

      <div {...panel('taxonomia')}>
        <TaxonomyStep
          projectId={projectId}
          editable={canBuild}
          selection={selection}
          onSelectionChange={select}
          domains={domains}
          onDomainsChange={setDomains}
          onUseTemplate={copyTemplateToManifest}
          copyError={copyError}
          manifest={canBuild ? manifestCard(true) : readOnlyManifest}
          notReady={notReady}
          onProfileDirty={onProfileDirty}
          onCopyProfile={copyProfileToManifest}
        />
      </div>

      {canBuild && (
        <div {...panel('construir')}>
          <BuildCard
            key={builtAt ?? 'nuevo'}
            project={project.data}
            context={built}
            selection={selection}
            domains={domains}
            notReady={notReady}
            leftoverFolder={leftoverFolder}
          />
        </div>
      )}

      {built && (
        <div {...panel('resultado')}>
          <Stack>
            <Summary
              context={built}
              canDelete={canDo(project.data, 'owner') && writable}
              onDelete={() => setDeleting(true)}
            />
            <Domains key={built.built_at} context={built} projectId={projectId} />
            <VersionsCard context={built} projectId={projectId} editable={canBuild} />
          </Stack>
        </div>
      )}

      {built && (
        <div {...panel('entregar')}>
          <Stack>
            <SiteCard context={built} projectId={projectId} />
            <DeliveryCard projectId={projectId} />
          </Stack>
        </div>
      )}

      <div {...panel('historial')}>
        <HistoryCard projectId={projectId} />
      </div>

      <UnsavedDraftGuard dirty={manifestDirty || profileDirty} />
      {deleting && (
        <DangerousOperationModal
          project={project.data}
          operation="context_delete"
          onClose={() => setDeleting(false)}
        />
      )}
      <ConfirmModal
        opened={confirm !== null}
        onClose={() => setConfirm(null)}
        title={t('context.manifest.replaceTitle')}
        message={confirm?.body}
        danger={false}
        confirmLabel={t('context.manifest.replace')}
        onConfirm={() => {
          confirm?.apply();
          setConfirm(null);
        }}
      />
    </Stack>
  );
}
