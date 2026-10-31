import { Anchor, Card, Center, Group, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { FolderBrowser } from '../../components/FolderBrowser';
import { formatDateTime } from '../../components/format';
import { StatusLight } from '../../components/StatusLight';
import { isAdminView, useLocation } from './useLocations';

const GB = 1024 ** 3;

/** Detalle de una ubicación con su explorador de carpetas. */
export function LocationDetailPage() {
  const { t } = useTranslation();
  const id = Number(useParams().locationId);
  const { data: location, isPending, isError, error } = useLocation(id);

  if (isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (isError) {
    return <ErrorAlert error={error} />;
  }

  const facts: [string, string][] = [
    [t('locations.fields.usage'), t(`locations.usage.${location.usage}`)],
    [t('locations.fields.access'), t(`locations.access.${location.access}`)],
    [t('locations.fields.kind'), t(`locations.kind.${location.kind}`)],
    [t('locations.fields.probedAt'), formatDateTime(location.probed_at)],
  ];
  if (isAdminView(location)) {
    facts.push(
      [t('locations.fields.containerPath'), location.container_path],
      [t('locations.fields.latency'), location.latency_ms === null ? '—' : `${location.latency_ms} ms`],
      [
        t('locations.fields.freeSpace'),
        location.free_bytes === null ? '—' : `${(location.free_bytes / GB).toFixed(1)} GB`,
      ],
    );
  }

  return (
    <Stack>
      <Anchor component={Link} to="/locations" size="sm">
        {t('locations.back')}
      </Anchor>
      <Group justify="space-between">
        <Title order={2}>{location.name}</Title>
        <StatusLight status={location.status} reasons={location.status_reasons} />
      </Group>
      {location.display_path && <Text c="dimmed">{location.display_path}</Text>}
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        {facts.map(([label, value]) => (
          <div key={label}>
            <Text size="xs" c="dimmed">
              {label}
            </Text>
            <Text size="sm">{value}</Text>
          </div>
        ))}
      </SimpleGrid>
      <Card withBorder>
        <Title order={3} size="h4" mb="sm">
          {t('locations.browse')}
        </Title>
        <FolderBrowser locationId={location.id} rootLabel={location.name} />
      </Card>
    </Stack>
  );
}
