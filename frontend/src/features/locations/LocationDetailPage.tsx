import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { FolderBrowser } from '../../components/FolderBrowser';
import { formatDateTime } from '../../components/format';
import { StatusLight } from '../../components/StatusLight';
import { type AnyLocation, isAdminView, useLocation, useUpdateLocation } from './useLocations';

const GB = 1024 ** 3;

/** Un patrón por línea; las líneas en blanco no cuentan. */
function parsePatterns(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line !== '');
}

/**
 * Patrones de nombre que no escanea ningún proyecto de una ubicación de origen (1.4.0). Los edita un administrador;
 * el resto solo los ve.
 */
function IgnorePatternsCard({ location }: { location: AnyLocation }) {
  const { t } = useTranslation();
  const update = useUpdateLocation();
  const current = location.ignore_patterns ?? [];
  const [text, setText] = useState(current.join('\n'));
  const admin = isAdminView(location);
  const changed = parsePatterns(text).join('\n') !== current.join('\n');
  return (
    <Card withBorder>
      <Title order={3} size="h4" mb="xs">
        {t('locations.patterns.title')}
      </Title>
      <Text size="sm" c="dimmed" mb="sm">
        {t('locations.patterns.intro')}
      </Text>
      {admin ? (
        <Stack gap="sm">
          <Alert color="yellow">{t('locations.patterns.warning')}</Alert>
          <Textarea
            label={t('locations.patterns.label')}
            description={t('locations.patterns.examples')}
            rows={6}
            value={text}
            onChange={(event) => setText(event.currentTarget.value)}
            styles={{ input: { fontFamily: 'var(--mantine-font-family-monospace)' } }}
          />
          {update.isError && <ErrorAlert error={update.error} />}
          <Group justify="flex-end">
            <Button
              disabled={!changed}
              loading={update.isPending}
              onClick={() =>
                update.mutate(
                  { id: location.id, body: { ignore_patterns: parsePatterns(text) } },
                  { onSuccess: (saved) => setText((saved.ignore_patterns ?? []).join('\n')) },
                )
              }
            >
              {t('locations.patterns.save')}
            </Button>
          </Group>
        </Stack>
      ) : current.length === 0 ? (
        <Text size="sm" c="dimmed">
          {t('locations.patterns.none')}
        </Text>
      ) : (
        <Group gap="xs">
          {current.map((pattern) => (
            <Badge key={pattern} variant="light" color="gray" tt="none" ff="monospace">
              {pattern}
            </Badge>
          ))}
        </Group>
      )}
    </Card>
  );
}

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
      {location.usage !== 'destination' && <IgnorePatternsCard location={location} />}
      <Card withBorder>
        <Title order={3} size="h4" mb="sm">
          {t('locations.browse')}
        </Title>
        <FolderBrowser locationId={location.id} rootLabel={location.name} />
      </Card>
    </Stack>
  );
}
