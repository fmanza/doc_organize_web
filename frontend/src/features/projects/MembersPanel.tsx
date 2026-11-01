import { Button, Group, Select, Stack, Table, Text, Title, VisuallyHidden } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import {
  type MemberRole,
  type ProjectOut,
  useAddMember,
  useMembers,
  useRemoveMember,
  useUpdateMember,
  type UserBrief,
  useUserLookup,
} from './useProjects';

const ROLES: MemberRole[] = ['owner', 'editor', 'viewer'];

/** Miembros del proyecto; el propietario invita, cambia roles y quita miembros (siempre queda un propietario). */
export function MembersPanel({ project }: { project: ProjectOut }) {
  const { t } = useTranslation();
  const isOwner = project.role === 'owner';
  const members = useMembers(project.id);
  const add = useAddMember(project.id);
  const update = useUpdateMember(project.id);
  const remove = useRemoveMember(project.id);
  const [search, setSearch] = useState('');
  const [chosen, setChosen] = useState<UserBrief | null>(null);
  const [role, setRole] = useState<MemberRole>('viewer');
  const lookup = useUserLookup(chosen ? '' : search);
  const candidates = (lookup.data?.items ?? []).filter(
    (u) => !members.data?.items.some((m) => m.user_id === u.id),
  );
  // El elegido se conserva aunque la búsqueda cambie al mostrar su etiqueta.
  const options = [...(chosen ? [chosen] : []), ...candidates.filter((u) => u.id !== chosen?.id)].map(
    (u) => ({
      value: String(u.id),
      label: `${u.display_name} (${u.username})`,
    }),
  );
  const roleOptions = ROLES.map((value) => ({ value, label: t(`projects.roles.${value}`) }));
  const mutationError = add.error ?? update.error ?? remove.error;

  return (
    <Stack>
      <Title order={3} size="h4">
        {t('projects.members.title')}
      </Title>
      {members.isError && <ErrorAlert error={members.error} />}
      {mutationError && <ErrorAlert error={mutationError} />}
      {members.data && (
        <Table.ScrollContainer minWidth={520}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('projects.members.user')}</Table.Th>
                <Table.Th>{t('projects.fields.role')}</Table.Th>
                {isOwner && (
                  <Table.Th>
                    <VisuallyHidden>{t('common.actions')}</VisuallyHidden>
                  </Table.Th>
                )}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {members.data.items.map((member) => (
                <Table.Tr key={member.user_id}>
                  <Table.Td>
                    {member.display_name}{' '}
                    <Text span size="sm" c="dimmed">
                      ({member.username})
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {isOwner ? (
                      <Select
                        aria-label={t('projects.members.roleOf', { name: member.username })}
                        data={roleOptions}
                        value={member.role}
                        allowDeselect={false}
                        onChange={(value) =>
                          value && update.mutate({ userId: member.user_id, role: value as MemberRole })
                        }
                        maw={180}
                      />
                    ) : (
                      t(`projects.roles.${member.role}`)
                    )}
                  </Table.Td>
                  {isOwner && (
                    <Table.Td>
                      <Button
                        size="xs"
                        variant="light"
                        color="red"
                        onClick={() => remove.mutate(member.user_id)}
                        aria-label={t('projects.members.removeLabel', { name: member.username })}
                      >
                        {t('projects.members.remove')}
                      </Button>
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {isOwner && (
        <Group align="flex-end">
          <Select
            label={t('projects.members.invite')}
            description={t('projects.members.inviteHint')}
            searchable
            data={options}
            filter={({ options: all }) => all}
            searchValue={search}
            onSearchChange={(value) => {
              setSearch(value);
              if (chosen && value !== options[0]?.label) {
                setChosen(null);
              }
            }}
            value={chosen ? String(chosen.id) : null}
            onChange={(value) => setChosen(candidates.find((u) => String(u.id) === value) ?? null)}
            nothingFoundMessage={search.trim().length >= 2 ? t('projects.members.noUsers') : undefined}
            maw={320}
          />
          <Select
            label={t('projects.fields.role')}
            data={roleOptions}
            value={role}
            allowDeselect={false}
            onChange={(value) => value && setRole(value as MemberRole)}
            maw={180}
          />
          <Button
            disabled={!chosen}
            loading={add.isPending}
            onClick={() =>
              chosen &&
              add.mutate(
                { user_id: chosen.id, role },
                {
                  onSuccess: () => {
                    setChosen(null);
                    setSearch('');
                  },
                },
              )
            }
          >
            {t('projects.members.add')}
          </Button>
        </Group>
      )}
    </Stack>
  );
}
