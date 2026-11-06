import { Anchor, Button, Center, Group, Loader, Stack, Table, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { PageControls } from '../../components/Paging';
import { SearchBox, SortableTh } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { RunStatusBadge } from '../runs/RunStatusBadge';
import { ProjectFormModal } from './ProjectFormModal';
import { type ProjectSort, useProjects } from './useProjects';

const PROJECT_SORT: readonly ProjectSort[] = ['name', 'source', 'destination', 'last_run'];

/** Lista y selector de proyectos (sustituye a `project_selector.html.j2`): los del usuario o, para un admin, todos. */
export function ProjectsPage() {
  const { t } = useTranslation();
  const list = useListState(PROJECT_SORT);
  const { paging, q } = list;
  const [creating, setCreating] = useState(false);
  const { data, isPending, isError, error } = useProjects(list.query);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('projects.title')}</Title>
        <Button onClick={() => setCreating(true)}>{t('projects.new')}</Button>
      </Group>
      <Text c="dimmed">{t('projects.intro')}</Text>
      <SearchBox value={q} onChange={list.setQ} label={t('projects.search')} />
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && data.items.length === 0 && (
        <Text c="dimmed">{t(q ? 'projects.noMatches' : 'projects.empty')}</Text>
      )}
      {data && data.items.length > 0 && (
        <Table.ScrollContainer minWidth={760}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <SortableTh state={list} sortKey="name">
                  {t('projects.fields.name')}
                </SortableTh>
                <SortableTh state={list} sortKey="source">
                  {t('projects.fields.source')}
                </SortableTh>
                <SortableTh state={list} sortKey="destination">
                  {t('projects.fields.destination')}
                </SortableTh>
                <Table.Th>{t('projects.fields.role')}</Table.Th>
                <SortableTh state={list} sortKey="last_run">
                  {t('projects.fields.lastRun')}
                </SortableTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.items.map((project) => (
                <Table.Tr key={project.id}>
                  <Table.Td>
                    <Anchor component={Link} to={`/projects/${project.id}`}>
                      {project.name}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>{project.source_location.name}</Table.Td>
                  <Table.Td>
                    {project.destination_location.name} / {project.destination_subpath}
                  </Table.Td>
                  <Table.Td>{t(`projects.roles.${project.role}`)}</Table.Td>
                  <Table.Td>
                    {project.last_run ? (
                      <Group gap="xs" wrap="nowrap">
                        <RunStatusBadge status={project.last_run.status} />
                        <Text size="sm">{formatDateTime(project.last_run.created_at)}</Text>
                      </Group>
                    ) : (
                      <Text size="sm" c="dimmed">
                        {t('projects.noRuns')}
                      </Text>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {data && <PageControls state={paging} total={data.total} label={t('paging.label')} />}
      {creating && <ProjectFormModal opened onClose={() => setCreating(false)} />}
    </Stack>
  );
}
