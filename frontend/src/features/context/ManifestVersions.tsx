import {
  Accordion,
  Anchor,
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  Textarea,
} from '@mantine/core';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import {
  type Manifest,
  type ManifestVersion,
  manifestVersionQuery,
  useManifestVersions,
  useRestoreManifest,
} from './useContext';

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
export function ManifestVersions({
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
