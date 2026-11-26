import { AppShell, Box, Burger, Group, NavLink, ScrollArea, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterNavLink, Outlet, useLocation, useMatch } from 'react-router';

import { UserMenu } from '../features/auth/UserMenu';
import { ColorSchemeSync } from './ColorSchemeSync';
import { LanguageSync } from './LanguageSync';
import { RunNotifier } from '../features/runs/RunNotifier';
import { Icon } from '../components/Icon';
import { NAV_ICON_SIZE, NAV_ICONS, type NavIconKey } from '../components/icons';
import { useMe } from '../features/auth/useAuth';
import { useProject } from '../features/projects/useProjects';
import { type AdminPage, visibleAdminMenu } from './adminMenu';
import { TenantSwitcher } from './TenantSwitcher';

/**
 * Secciones de un proyecto: solo se muestran con un proyecto abierto, porque sus rutas cuelgan de su id. Duplicados la
 * primera (decisión del mantenedor, Fase 10).
 */
const PROJECT_SECTIONS = [
  'duplicates',
  'scan',
  'documents',
  'context',
] as const satisfies readonly NavIconKey[];

/** Icono de una entrada del menú (decorativo: el nombre accesible es el texto). */
function navIcon(key: NavIconKey) {
  return <Icon of={NAV_ICONS[key]} size={NAV_ICON_SIZE} />;
}

/**
 * El proyecto abierto y sus secciones, bajo «Proyectos» (2.1.1). Antes eran hijos del enlace «Proyectos», y un
 * `NavLink` de Mantine con hijos no navega: con un proyecto abierto ya no se podía volver a la lista. Si el proyecto
 * no existe o se ha borrado (la API da 404 y al terminar un borrado se invalida su consulta), el bloque no se muestra,
 * en vez de quedar con enlaces a un proyecto que ya no está.
 */
function ProjectNav({ projectId }: { projectId: number }) {
  const { t } = useTranslation();
  const project = useProject(projectId);
  if (!project.data) {
    return null;
  }
  return (
    <Stack gap={0} pl="md" role="group" aria-label={t('nav.currentProject', { name: project.data.name })}>
      <NavLink
        component={RouterNavLink}
        to={`/projects/${projectId}`}
        label={project.data.name}
        description={t('nav.project')}
        leftSection={navIcon('project')}
        end
      />
      {PROJECT_SECTIONS.map((key) => (
        <NavLink
          key={key}
          component={RouterNavLink}
          to={`/projects/${projectId}/${key}`}
          label={t(`nav.${key}`)}
          leftSection={navIcon(key)}
          pl="lg"
        />
      ))}
    </Stack>
  );
}

function AdminLink({ page }: { page: AdminPage }) {
  const { t } = useTranslation();
  return (
    <NavLink
      component={RouterNavLink}
      to={page.to}
      label={t(`nav.${page.key}`)}
      leftSection={navIcon(page.key)}
    />
  );
}

/** Grupo plegable; se abre solo cuando la página actual es suya (como «Proyectos»). */
function AdminGroup({ group, pages }: { group: NavIconKey; pages: AdminPage[] }) {
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
      leftSection={navIcon(group)}
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
  const { pathname } = useLocation();
  // En pantallas estrechas el menú se abre con el botón y se pliega al navegar: se guarda en qué ruta se abrió, y en
  // cuanto la ruta cambia deja de estar abierto (sin efectos). En pantallas anchas siempre se ve.
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const navOpened = openedAt === pathname;
  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 240, breakpoint: 'sm', collapsed: { mobile: !navOpened } }}
      padding="md"
    >
      <RunNotifier />
      <ColorSchemeSync />
      <LanguageSync />
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap" miw={0}>
            <Burger
              opened={navOpened}
              onClick={() => setOpenedAt(navOpened ? null : pathname)}
              hiddenFrom="sm"
              size="sm"
              aria-label={t(navOpened ? 'nav.close' : 'nav.open')}
              aria-expanded={navOpened}
              aria-controls="app-navbar"
            />
            {/* Por debajo de `sm`, el título abreviado; el nombre accesible es siempre el completo. */}
            <Title
              order={1}
              size="h3"
              aria-label={t('app.title')}
              style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
            >
              <Box component="span" visibleFrom="sm">
                {t('app.title')}
              </Box>
              <Box component="span" hiddenFrom="sm" aria-hidden>
                {t('app.shortTitle')}
              </Box>
            </Title>
          </Group>
          <Group gap="xs" wrap="nowrap" style={{ flexShrink: 0 }}>
            <TenantSwitcher />
            <UserMenu />
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar id="app-navbar" p="sm" aria-label={t('nav.label')}>
        {/* Con todos los enlaces de administración no cabe en pantallas bajas: se desplaza (WCAG 1.4.10). */}
        <AppShell.Section grow component={ScrollArea} type="auto">
          <Stack gap={4}>
            <NavLink
              component={RouterNavLink}
              to="/"
              label={t('nav.home')}
              leftSection={navIcon('home')}
              end
            />
            <NavLink
              component={RouterNavLink}
              to="/projects"
              label={t('nav.projects')}
              leftSection={navIcon('projects')}
              end
            />
            {projectId !== undefined && Number.isInteger(Number(projectId)) && (
              <ProjectNav projectId={Number(projectId)} />
            )}
            <NavLink
              component={RouterNavLink}
              to="/runs"
              label={t('nav.runs')}
              leftSection={navIcon('runs')}
            />
            <NavLink
              component={RouterNavLink}
              to="/locations"
              label={t('nav.locations')}
              leftSection={navIcon('locations')}
            />
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
