import { AppShell, Group, NavLink, ScrollArea, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterNavLink, Outlet, useMatch } from 'react-router';

import { UserMenu } from '../features/auth/UserMenu';
import { RunNotifier } from '../features/runs/RunNotifier';
import { can, type Permission, useMe } from '../features/auth/useAuth';
import { TenantSwitcher } from './TenantSwitcher';

/**
 * Secciones de un proyecto: solo se muestran con un proyecto abierto, porque sus rutas cuelgan de su id. Duplicados la
 * primera (decisión del mantenedor, Fase 10).
 */
const PROJECT_SECTIONS = ['duplicates', 'scan', 'documents', 'context'] as const;

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
  const projectId = useMatch('/projects/:projectId/*')?.params.projectId;
  const adminSections = ADMIN_SECTIONS.filter((section) =>
    section.instance ? me?.is_instance_admin : section.permission ? can(me, section.permission) : false,
  );
  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 240, breakpoint: 'sm' }} padding="md">
      <RunNotifier />
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
            <NavLink
              component={RouterNavLink}
              to="/projects"
              label={t('nav.projects')}
              end={projectId !== undefined}
              opened={projectId !== undefined}
            >
              {projectId !== undefined &&
                PROJECT_SECTIONS.map((key) => (
                  <NavLink
                    key={key}
                    component={RouterNavLink}
                    to={`/projects/${projectId}/${key}`}
                    label={t(`nav.${key}`)}
                  />
                ))}
            </NavLink>
            <NavLink component={RouterNavLink} to="/runs" label={t('nav.runs')} />
            <NavLink component={RouterNavLink} to="/locations" label={t('nav.locations')} />
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
