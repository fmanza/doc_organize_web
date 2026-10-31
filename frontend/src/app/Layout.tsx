import { AppShell, Badge, Group, NavLink, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterNavLink, Outlet } from 'react-router';

// Secciones del ROADMAP: se habilitan al implementar su fase.
const SECTIONS: { key: string; phase: number }[] = [
  { key: 'locations', phase: 2 },
  { key: 'projects', phase: 3 },
  { key: 'runs', phase: 3 },
  { key: 'scan', phase: 4 },
  { key: 'cache', phase: 5 },
  { key: 'duplicates', phase: 6 },
  { key: 'context', phase: 7 },
  { key: 'ai', phase: 8 },
];

export function Layout() {
  const { t } = useTranslation();
  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 240, breakpoint: 'sm' }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Title order={1} size="h3">
            {t('app.title')}
          </Title>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm" aria-label={t('nav.label')}>
        <Stack gap={4}>
          <NavLink component={RouterNavLink} to="/" label={t('nav.home')} end />
          {SECTIONS.map((section) => (
            <NavLink
              key={section.key}
              label={t(`nav.${section.key}`)}
              disabled
              rightSection={
                <Badge size="xs" variant="light">
                  {t('nav.phase', { phase: section.phase })}
                </Badge>
              }
            />
          ))}
        </Stack>
        <Text size="xs" c="dimmed" mt="auto">
          v{__APP_VERSION__}
        </Text>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
