import { AppShell, Badge, Group, NavLink, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterNavLink, Outlet } from 'react-router';

import { UserMenu } from '../features/auth/UserMenu';
import { useMe } from '../features/auth/useAuth';

// Secciones del ROADMAP: se habilitan al implementar su fase.
const SECTIONS: { key: string; phase: number }[] = [
  { key: 'scan', phase: 4 },
  { key: 'cache', phase: 5 },
  { key: 'duplicates', phase: 6 },
  { key: 'context', phase: 7 },
  { key: 'ai', phase: 8 },
];

const ADMIN_SECTIONS = ['users', 'sessions', 'audit', 'settings'] as const;

export function Layout() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 240, breakpoint: 'sm' }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Title order={1} size="h3">
            {t('app.title')}
          </Title>
          <UserMenu />
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm" aria-label={t('nav.label')}>
        <Stack gap={4}>
          <NavLink component={RouterNavLink} to="/" label={t('nav.home')} end />
          <NavLink component={RouterNavLink} to="/projects" label={t('nav.projects')} />
          <NavLink component={RouterNavLink} to="/runs" label={t('nav.runs')} />
          <NavLink component={RouterNavLink} to="/locations" label={t('nav.locations')} />
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
          {me?.role === 'admin' && (
            <>
              <Text size="xs" fw={700} c="dimmed" mt="md" px="sm">
                {t('nav.admin')}
              </Text>
              {ADMIN_SECTIONS.map((key) => (
                <NavLink key={key} component={RouterNavLink} to={`/admin/${key}`} label={t(`nav.${key}`)} />
              ))}
            </>
          )}
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
