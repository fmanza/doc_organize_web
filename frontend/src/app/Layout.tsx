import {
  ActionIcon,
  AppShell,
  Box,
  Burger,
  Divider,
  Group,
  NavLink,
  ScrollArea,
  Stack,
  Text,
  Title,
  Tooltip,
  VisuallyHidden,
  useMantineTheme,
} from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { createContext, useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink as RouterNavLink, Outlet, useLocation, useMatch } from 'react-router';

import { UserMenu } from '../features/auth/UserMenu';
import { ColorSchemeSync } from './ColorSchemeSync';
import { LanguageSync } from './LanguageSync';
import { RunNotifier } from '../features/runs/RunNotifier';
import { Icon } from '../components/Icon';
import { NAV_ICON_SIZE, NAV_ICONS, NAV_RAIL_ICONS, type NavIconKey } from '../components/icons';
import { useMe } from '../features/auth/useAuth';
import { useProject } from '../features/projects/useProjects';
import { type AdminPage, visibleAdminMenu } from './adminMenu';
import { TenantSwitcher } from './TenantSwitcher';
import { useNavRail } from './navRail';

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

/** Ancho del menú lateral desplegado y contraído a una barra de iconos. */
const NAVBAR_WIDTH = 240;
const RAIL_WIDTH = 64;

/** Si el menú se pinta como barra de iconos (contraído, y solo en pantallas anchas). */
const RailContext = createContext(false);

/** En la barra de iconos, el icono centrado y sin el hueco que lo separa del texto. */
const RAIL_STYLES = {
  root: { justifyContent: 'center' },
  section: { marginInlineEnd: 0 },
  body: { flex: 0 },
} as const;

/** Icono de una entrada del menú (decorativo: el nombre accesible es el texto). */
function navIcon(key: NavIconKey) {
  return <Icon of={NAV_ICONS[key]} size={NAV_ICON_SIZE} />;
}

interface NavItemProps {
  to: string;
  label: string;
  icon: NavIconKey;
  end?: boolean;
  description?: string;
  /** Sangría en el menú desplegado (en la barra de iconos no la hay). */
  indent?: 'md' | 'lg';
  /** Texto del aviso en la barra de iconos si no basta con `label`. */
  tooltip?: string;
}

/**
 * Entrada del menú. En la barra de iconos el texto sigue en el enlace, oculto a la vista pero no a los lectores de
 * pantalla (es su nombre accesible), y se ve en un aviso al pasar el ratón o llevar el foco (WCAG 1.4.13: se cierra
 * con Escape y no tapa el enlace).
 */
function NavItem({ to, label, icon, end = false, description, indent, tooltip }: NavItemProps) {
  const rail = useContext(RailContext);
  if (!rail) {
    return (
      <NavLink
        component={RouterNavLink}
        to={to}
        label={label}
        description={description}
        leftSection={navIcon(icon)}
        end={end}
        {...(indent ? { pl: indent } : {})}
      />
    );
  }
  return (
    <Tooltip
      label={tooltip ?? label}
      position="right"
      withArrow
      events={{ hover: true, focus: true, touch: false }}
    >
      <NavLink
        component={RouterNavLink}
        to={to}
        label={<VisuallyHidden>{label}</VisuallyHidden>}
        leftSection={navIcon(icon)}
        end={end}
        styles={RAIL_STYLES}
      />
    </Tooltip>
  );
}

/**
 * El proyecto abierto y sus secciones, bajo «Proyectos» (2.1.1). Antes eran hijos del enlace «Proyectos», y un
 * `NavLink` de Mantine con hijos no navega: con un proyecto abierto ya no se podía volver a la lista. Si el proyecto
 * no existe o se ha borrado (la API da 404 y al terminar un borrado se invalida su consulta), el bloque no se muestra,
 * en vez de quedar con enlaces a un proyecto que ya no está.
 */
function ProjectNav({ projectId }: { projectId: number }) {
  const { t } = useTranslation();
  const rail = useContext(RailContext);
  const project = useProject(projectId);
  if (!project.data) {
    return null;
  }
  const name = t('nav.currentProject', { name: project.data.name });
  return (
    <Stack gap={0} pl={rail ? 0 : 'md'} role="group" aria-label={name}>
      <NavItem
        to={`/projects/${projectId}`}
        label={project.data.name}
        description={t('nav.project')}
        tooltip={name}
        icon="project"
        end
      />
      {PROJECT_SECTIONS.map((key) => (
        <NavItem
          key={key}
          to={`/projects/${projectId}/${key}`}
          label={t(`nav.${key}`)}
          icon={key}
          indent="lg"
        />
      ))}
    </Stack>
  );
}

function AdminLink({ page }: { page: AdminPage }) {
  const { t } = useTranslation();
  return <NavItem to={page.to} label={t(`nav.${page.key}`)} icon={page.key} />;
}

/**
 * Grupo plegable; se abre solo cuando la página actual es suya (como «Proyectos»). En la barra de iconos no hay sitio
 * para desplegar: sus páginas se muestran seguidas, como un grupo con nombre para los lectores de pantalla.
 */
function AdminGroup({ group, pages }: { group: NavIconKey; pages: AdminPage[] }) {
  const rail = useContext(RailContext);
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const [toggled, setToggled] = useState(false);
  const current = pages.some((page) => pathname === page.to || pathname.startsWith(`${page.to}/`));
  const opened = current || toggled;
  if (rail) {
    return (
      <Stack gap={4} role="group" aria-label={t(`nav.${group}`)}>
        {pages.map((page) => (
          <AdminLink key={page.key} page={page} />
        ))}
      </Stack>
    );
  }
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
  // En pantallas anchas el menú se puede contraer a una barra de iconos (se recuerda en este navegador). En las
  // estrechas no: allí el menú ocupa la pantalla al abrirlo y siempre lleva los textos.
  const theme = useMantineTheme();
  const wide = useMediaQuery(`(min-width: ${theme.breakpoints.sm})`, false, {
    getInitialValueInEffect: false,
  });
  const [railPreferred, setRailPreferred] = useNavRail();
  const rail = wide && railPreferred;
  const railToggle = t(rail ? 'nav.expand' : 'nav.collapse');
  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: rail ? RAIL_WIDTH : NAVBAR_WIDTH,
        breakpoint: 'sm',
        collapsed: { mobile: !navOpened },
      }}
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
            {wide && (
              <Tooltip label={railToggle}>
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  size="lg"
                  onClick={() => setRailPreferred(!rail)}
                  aria-label={railToggle}
                  aria-expanded={!rail}
                  aria-controls="app-navbar"
                >
                  <Icon of={rail ? NAV_RAIL_ICONS.expand : NAV_RAIL_ICONS.collapse} size={NAV_ICON_SIZE} />
                </ActionIcon>
              </Tooltip>
            )}
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
        <RailContext.Provider value={rail}>
          {/* Con todos los enlaces de administración no cabe en pantallas bajas: se desplaza (WCAG 1.4.10). */}
          <AppShell.Section grow component={ScrollArea} type="auto">
            <Stack gap={4}>
              <NavItem to="/" label={t('nav.home')} icon="home" end />
              <NavItem to="/projects" label={t('nav.projects')} icon="projects" end />
              {projectId !== undefined && Number.isInteger(Number(projectId)) && (
                <ProjectNav projectId={Number(projectId)} />
              )}
              <NavItem to="/runs" label={t('nav.runs')} icon="runs" />
              <NavItem to="/locations" label={t('nav.locations')} icon="locations" />
              {adminMenu.length > 0 && (
                <>
                  {rail ? (
                    <Divider my="xs" />
                  ) : (
                    <Text size="xs" fw={700} c="dimmed" mt="md" px="sm">
                      {t('nav.admin')}
                    </Text>
                  )}
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
          {!rail && (
            <AppShell.Section pt="xs">
              <Text size="xs" c="dimmed">
                v{__APP_VERSION__}
              </Text>
            </AppShell.Section>
          )}
        </RailContext.Provider>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
