import {
  Anchor,
  Button,
  Center,
  Group,
  Loader,
  Pagination,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { RunStatusBadge } from '../runs/RunStatusBadge';
import { ProjectFormModal } from './ProjectFormModal';
import { PROJECTS_PAGE_SIZE, useProjects } from './useProjects';

/** Lista y selector de proyectos (sustituye a `project_selector.html.j2`): los del usuario o, para un admin, todos. */
export function ProjectsPage() {
  const { t } = useTranslation();
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const { data, isPending, isError, error } = useProjects(q, page);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('projects.title')}</Title>
        <Button onClick={() => setCreating(true)}>{t('projects.new')}</Button>
      </Group>
      <Text c="dimmed">{t('projects.intro')}</Text>
      <TextInput
        label={t('projects.search')}
        value={q}
        onChange={(event) => {
          setQ(event.currentTarget.value);
          setPage(1);
        }}
        maw={360}
      />
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
                <Table.Th>{t('projects.fields.name')}</Table.Th>
                <Table.Th>{t('projects.fields.source')}</Table.Th>
                <Table.Th>{t('projects.fields.destination')}</Table.Th>
                <Table.Th>{t('projects.fields.role')}</Table.Th>
                <Table.Th>{t('projects.fields.lastRun')}</Table.Th>
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
      {data && data.total > PROJECTS_PAGE_SIZE && (
        <Pagination total={Math.ceil(data.total / PROJECTS_PAGE_SIZE)} value={page} onChange={setPage} />
      )}
      {creating && <ProjectFormModal opened onClose={() => setCreating(false)} />}
    </Stack>
  );
}
