import { AppShell, Badge, Group, NavLink, ScrollArea, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterNavLink, Outlet } from 'react-router';

import { UserMenu } from '../features/auth/UserMenu';
import { can, type Permission, useMe } from '../features/auth/useAuth';
import { TenantSwitcher } from './TenantSwitcher';

// Secciones del ROADMAP: se habilitan al implementar su fase.
const SECTIONS: { key: string; phase: number }[] = [
  { key: 'scan', phase: 4 },
  { key: 'cache', phase: 5 },
  { key: 'duplicates', phase: 6 },
  { key: 'context', phase: 7 },
];

/** Secciones de administración con lo que exige cada una (las mismas guardas que el router). */
const ADMIN_SECTIONS: { key: string; permission?: Permission; instance?: boolean }[] = [
  { key: 'tenants', instance: true },
  { key: 'users', permission: 'users.manage' },
  { key: 'roles', permission: 'roles.manage' },
  { key: 'sessions', permission: 'users.manage' },
  { key: 'audit', permission: 'audit.read' },
  { key: 'taxonomy-templates', permission: 'templates.manage' },
  { key: 'settings', instance: true },
  { key: 'ai-settings', instance: true },
  { key: 'ai-usage', instance: true },
];

export function Layout() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const adminSections = ADMIN_SECTIONS.filter((section) =>
    section.instance ? me?.is_instance_admin : section.permission ? can(me, section.permission) : false,
  );
  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 240, breakpoint: 'sm' }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Title order={1} size="h3">
            {t('app.title')}
          </Title>
          <Group gap="sm">
            <TenantSwitcher />
            <UserMenu />
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm" aria-label={t('nav.label')}>
        {/* Con todos los enlaces de administración no cabe en pantallas bajas: se desplaza (WCAG 1.4.10). */}
        <AppShell.Section grow component={ScrollArea} type="auto">
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
            {adminSections.length > 0 && (
              <>
                <Text size="xs" fw={700} c="dimmed" mt="md" px="sm">
                  {t('nav.admin')}
                </Text>
                {adminSections.map(({ key }) => (
                  <NavLink key={key} component={RouterNavLink} to={`/admin/${key}`} label={t(`nav.${key}`)} />
                ))}
              </>
            )}
          </Stack>
        </AppShell.Section>
        <AppShell.Section pt="xs">
          <Text size="xs" c="dimmed">
            v{__APP_VERSION__}
          </Text>
        </AppShell.Section>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
