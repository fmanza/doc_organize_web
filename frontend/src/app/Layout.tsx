import { AppShell, Group, NavLink, ScrollArea, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterNavLink, Outlet, useLocation, useMatch } from 'react-router';

import { UserMenu } from '../features/auth/UserMenu';
import { RunNotifier } from '../features/runs/RunNotifier';
import { useMe } from '../features/auth/useAuth';
import { type AdminPage, visibleAdminMenu } from './adminMenu';
import { TenantSwitcher } from './TenantSwitcher';

/**
 * Secciones de un proyecto: solo se muestran con un proyecto abierto, porque sus rutas cuelgan de su id. Duplicados la
 * primera (decisión del mantenedor, Fase 10).
 */
const PROJECT_SECTIONS = ['duplicates', 'scan', 'documents', 'context'] as const;

function AdminLink({ page }: { page: AdminPage }) {
  const { t } = useTranslation();
  return <NavLink component={RouterNavLink} to={page.to} label={t(`nav.${page.key}`)} />;
}

/** Grupo plegable; se abre solo cuando la página actual es suya (como «Proyectos»). */
function AdminGroup({ group, pages }: { group: string; pages: AdminPage[] }) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const [toggled, setToggled] = useState(false);
  const current = pages.some((page) => pathname === page.to || pathname.startsWith(`${page.to}/`));
  const opened = current || toggled;
  // Botón (no un `<a>` sin destino) para que el lector de pantalla lo anuncie como desplegable.
  return (
    <NavLink
      component="button"
      type="button"
      aria-expanded={opened}
      label={t(`nav.${group}`)}
      opened={opened}
      onChange={setToggled}
      childrenOffset="md"
    >
      {pages.map((page) => (
        <AdminLink key={page.key} page={page} />
      ))}
    </NavLink>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const projectId = useMatch('/projects/:projectId/*')?.params.projectId;
  const adminMenu = visibleAdminMenu(me);
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
            {adminMenu.length > 0 && (
              <>
                <Text size="xs" fw={700} c="dimmed" mt="md" px="sm">
                  {t('nav.admin')}
                </Text>
                {adminMenu.map((entry) =>
                  'group' in entry ? (
                    <AdminGroup key={entry.group} group={entry.group} pages={entry.pages} />
                  ) : (
                    <AdminLink key={entry.key} page={entry} />
                  ),
                )}
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
