import {
  Anchor,
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { PageControls } from '../../components/Paging';
import { SearchBox, SortableTh } from '../../components/listing';
import { useListState } from '../../components/useListState';
import { formatDateTime } from '../../components/format';
import { StatusLight } from '../../components/StatusLight';
import { useMe } from '../auth/useAuth';
import { LocationFormModal } from './LocationFormModal';
import {
  type AnyLocation,
  isAdminView,
  type LocationOut,
  useDeleteLocation,
  useLocations,
  useProbeLocation,
  type LocationSort,
} from './useLocations';

const LOCATION_SORT: readonly LocationSort[] = ['name', 'usage', 'access', 'status', 'probed_at'];

type Editing = { location: LocationOut | null } | null;

/** Ubicaciones registradas: cualquier usuario las ve y explora; un admin las registra, edita, comprueba y borra. */
export function LocationsPage() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const isAdmin = !!me?.is_instance_admin; // las ubicaciones las registra el admin de instancia (E1)
  const list = useListState(LOCATION_SORT);
  const { paging } = list;
  const { data, isPending, isError, error } = useLocations(list.query);
  const probe = useProbeLocation();
  const remove = useDeleteLocation();
  const [editing, setEditing] = useState<Editing>(null);
  const [deleting, setDeleting] = useState<AnyLocation | null>(null);
  const [confirmName, setConfirmName] = useState('');

  const closeDelete = () => {
    setDeleting(null);
    setConfirmName('');
    remove.reset();
  };

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('locations.title')}</Title>
        {isAdmin && <Button onClick={() => setEditing({ location: null })}>{t('locations.new')}</Button>}
      </Group>
      <Text c="dimmed">{t(isAdmin ? 'locations.introAdmin' : 'locations.intro')}</Text>
      <SearchBox value={list.q} onChange={list.setQ} label={t('locations.search')} />
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {probe.isError && <ErrorAlert error={probe.error} />}
      {data && data.items.length === 0 && (
        <Text c="dimmed">
          {t(list.q ? 'listing.empty' : isAdmin ? 'locations.emptyAdmin' : 'locations.empty')}
        </Text>
      )}
      {data && data.items.length > 0 && (
        <Table.ScrollContainer minWidth={760}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <SortableTh state={list} sortKey="name">
                  {t('locations.fields.name')}
                </SortableTh>
                <SortableTh state={list} sortKey="usage">
                  {t('locations.fields.usage')}
                </SortableTh>
                <SortableTh state={list} sortKey="access">
                  {t('locations.fields.access')}
                </SortableTh>
                <SortableTh state={list} sortKey="status">
                  {t('locations.fields.status')}
                </SortableTh>
                <SortableTh state={list} sortKey="probed_at">
                  {t('locations.fields.probedAt')}
                </SortableTh>
                <Table.Th>
                  <VisuallyHidden>{t('common.actions')}</VisuallyHidden>
                </Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.items.map((location) => (
                <Table.Tr key={location.id}>
                  <Table.Td>
                    <Anchor component={Link} to={`/locations/${location.id}`}>
                      {location.name}
                    </Anchor>
                    {location.display_path && (
                      <Text size="xs" c="dimmed">
                        {location.display_path}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>{t(`locations.usage.${location.usage}`)}</Table.Td>
                  <Table.Td>{t(`locations.access.${location.access}`)}</Table.Td>
                  <Table.Td>
                    <StatusLight status={location.status} reasons={location.status_reasons} />
                  </Table.Td>
                  <Table.Td>{formatDateTime(location.probed_at)}</Table.Td>
                  <Table.Td>
                    {isAdmin && isAdminView(location) && (
                      <Group gap="xs" wrap="nowrap">
                        <Button
                          size="xs"
                          variant="light"
                          loading={probe.isPending && probe.variables === location.id}
                          onClick={() => probe.mutate(location.id)}
                          aria-label={t('locations.probeLabel', { name: location.name })}
                        >
                          {t('locations.probe')}
                        </Button>
                        <Button
                          size="xs"
                          variant="default"
                          onClick={() => setEditing({ location })}
                          aria-label={t('locations.editLabel', { name: location.name })}
                        >
                          {t('common.edit')}
                        </Button>
                        <Button
                          size="xs"
                          color="red"
                          variant="light"
                          onClick={() => setDeleting(location)}
                          aria-label={t('locations.deleteLabel', { name: location.name })}
                        >
                          {t('locations.delete')}
                        </Button>
                      </Group>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {data && <PageControls state={paging} total={data.total} label={t('locations.pages')} />}
      {editing && (
        <LocationFormModal
          key={editing.location?.id ?? 'new'}
          location={editing.location}
          opened
          onClose={() => setEditing(null)}
        />
      )}
      <Modal opened={deleting !== null} onClose={closeDelete} title={t('locations.deleteTitle')}>
        {deleting && (
          <Stack>
            <Text>{t('locations.deleteBody', { name: deleting.name })}</Text>
            <TextInput
              label={t('locations.deleteConfirm', { name: deleting.name })}
              value={confirmName}
              onChange={(event) => setConfirmName(event.currentTarget.value)}
              autoComplete="off"
            />
            {remove.isError && <ErrorAlert error={remove.error} />}
            <Group justify="flex-end">
              <Button variant="default" onClick={closeDelete}>
                {t('common.cancel')}
              </Button>
              <Button
                color="red"
                disabled={confirmName !== deleting.name}
                loading={remove.isPending}
                onClick={() => remove.mutate(deleting.id, { onSuccess: closeDelete })}
              >
                {t('locations.delete')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
