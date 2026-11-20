import { Badge, Button, Card, Group, Stack, Table, Text, Title } from '@mantine/core';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { api, unwrap } from '../../api/client';
import { ErrorAlert } from '../../components/ErrorAlert';
import type { ContextOut } from './useContext';

/**
 * Versiones de un documento (W6, doc_organize 2.0 F5): los grupos de la última construcción, con la vigente y si una
 * persona la confirmó; «Marcar como vigente» guarda la decisión `set_current_version`, que se aplica al reconstruir.
 */
export function VersionsCard({
  context,
  projectId,
  editable,
}: {
  context: ContextOut;
  projectId: number;
  editable: boolean;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [decided, setDecided] = useState<string[]>([]);
  const decide = useMutation({
    mutationFn: async (documentKey: string) =>
      unwrap(
        await api.POST('/api/v1/projects/{project_id}/context/decisions', {
          params: { path: { project_id: projectId } },
          body: { document_key: documentKey, action: 'set_current_version' },
        }),
      ),
    onSuccess: (_, documentKey) => {
      setDecided((current) => [...current, documentKey]);
      return queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'context', 'review'] });
    },
  });
  const groups = context.version_groups ?? [];
  const superseded = context.superseded_count ?? 0;
  if (groups.length === 0 && superseded === 0) {
    return null;
  }
  return (
    <Card withBorder component="section" aria-label={t('context.versions.title')}>
      <Title order={3} size="h4" mb="xs">
        {t('context.versions.title')}
      </Title>
      <Text size="sm" c="dimmed">
        {t('context.versions.intro')}
        {context.versions_mode && ` ${t(`context.versions.mode.${context.versions_mode}`)}`}
      </Text>
      {superseded > 0 && (
        <Text component="details" size="sm" mt="xs">
          <summary style={{ cursor: 'pointer' }}>
            {t('context.versions.superseded', { count: superseded })}
          </summary>
          <Stack gap={0} mt={2}>
            {(context.superseded ?? []).map((path) => (
              <Text key={path} size="xs" ff="monospace">
                {path}
              </Text>
            ))}
          </Stack>
        </Text>
      )}
      {decide.isError && <ErrorAlert error={decide.error} mt="xs" />}
      <Table mt="xs">
        <Table.Tbody>
          {groups.map((group) => (
            <Table.Tr key={group.key}>
              <Table.Td>
                <Stack gap={2}>
                  {group.members.map((member, index) => {
                    const current = member === group.current;
                    return (
                      <Group key={member} gap={6}>
                        <Text size="xs" ff="monospace" style={{ wordBreak: 'break-all' }}>
                          {member}
                        </Text>
                        <Badge size="xs" variant="outline" color="gray" tt="none">
                          v{group.versions[index]}
                        </Badge>
                        {current && (
                          <Badge size="xs" variant="light" color={group.confirmed ? 'teal' : 'blue'}>
                            {t('context.versions.current')} ·{' '}
                            {t(group.confirmed ? 'context.versions.confirmed' : 'context.versions.proposed')}
                          </Badge>
                        )}
                        {!current && editable && !decided.includes(member) && (
                          <Button
                            size="compact-xs"
                            variant="subtle"
                            loading={decide.isPending && decide.variables === member}
                            onClick={() => decide.mutate(member)}
                            aria-label={t('context.versions.setCurrentLabel', { path: member })}
                          >
                            {t('context.versions.setCurrent')}
                          </Button>
                        )}
                        {decided.includes(member) && (
                          <Text size="xs" c="teal">
                            {t('context.versions.pending')}
                          </Text>
                        )}
                      </Group>
                    );
                  })}
                </Stack>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Card>
  );
}
