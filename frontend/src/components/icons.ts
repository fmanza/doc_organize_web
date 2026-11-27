/**
 * Único punto de la app que importa `@tabler/icons-react` (lo impone ESLint con `no-restricted-imports`): aquí se elige
 * qué icono representa cada cosa y con qué tamaño. Cambiar un icono, o la librería, toca solo este fichero.
 *
 * Todos son decorativos: quien los pinta les pone `aria-hidden` y deja el texto al lado, que es el nombre accesible
 * (los estados nunca dependen solo del icono ni del color, WCAG 1.4.1). Usan `currentColor`, así que siguen el color
 * del texto y el tema claro u oscuro.
 */
import {
  IconAdjustmentsHorizontal,
  IconAlertTriangle,
  IconArrowLeft,
  IconArrowsSort,
  IconArrowUp,
  IconBuilding,
  IconChartBar,
  IconCheck,
  IconCircleCheck,
  IconCircleX,
  IconClock,
  IconCopy,
  IconDeviceDesktop,
  IconDevices,
  IconDots,
  IconFileText,
  IconFolder,
  IconFolders,
  IconHelpCircle,
  IconHome,
  IconInfoCircle,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconStethoscope,
  IconListSearch,
  IconMoon,
  IconPlayerPlay,
  IconPlayerStop,
  IconPlugConnected,
  IconScan,
  IconServer,
  IconSettings,
  IconShieldCheck,
  IconSitemap,
  IconSortAscending,
  IconSortDescending,
  IconSparkles,
  IconSun,
  IconTemplate,
  IconUser,
  IconUsers,
  IconX,
} from '@tabler/icons-react';

export type AppIcon = typeof IconHome;

/** Tamaño en el menú lateral. */
export const NAV_ICON_SIZE = 18;
/** Tamaño en distintivos, botones pequeños y cabeceras de tabla. */
export const SMALL_ICON_SIZE = 14;
/** Trazo algo más fino que el de Tabler (2) para que el menú no pese. */
export const ICON_STROKE = 1.75;

/** Entradas del menú lateral (`nav.<clave>` en las traducciones). */
export const NAV_ICONS = {
  home: IconHome,
  projects: IconFolders,
  project: IconFolder,
  duplicates: IconCopy,
  scan: IconScan,
  documents: IconFileText,
  context: IconSitemap,
  runs: IconPlayerPlay,
  locations: IconServer,
  access: IconUsers,
  users: IconUser,
  roles: IconShieldCheck,
  sessions: IconDevices,
  tenants: IconBuilding,
  'taxonomy-templates': IconTemplate,
  ai: IconSparkles,
  'ai-settings': IconPlugConnected,
  'ai-parameters': IconAdjustmentsHorizontal,
  'ai-usage': IconChartBar,
  settings: IconSettings,
  info: IconInfoCircle,
  diagnostics: IconStethoscope,
  audit: IconListSearch,
} as const satisfies Record<string, AppIcon>;

export type NavIconKey = keyof typeof NAV_ICONS;

/** Estado de una ejecución. */
export const RUN_STATUS_ICONS = {
  queued: IconClock,
  running: IconPlayerPlay,
  succeeded: IconCheck,
  failed: IconX,
  cancelled: IconPlayerStop,
} as const satisfies Record<string, AppIcon>;

/** Semáforo de ubicaciones y salud. */
export const LIGHT_ICONS = {
  ok: IconCircleCheck,
  degraded: IconAlertTriangle,
  unavailable: IconCircleX,
  unknown: IconHelpCircle,
} as const satisfies Record<string, AppIcon>;

/** Orden de las listas: ascendente, descendente y columna sin ordenar. */
export const SORT_ICONS = {
  asc: IconSortAscending,
  desc: IconSortDescending,
  none: IconArrowsSort,
} as const satisfies Record<string, AppIcon>;

/** Tema de la interfaz en el menú de usuario (2.3); la opción elegida lleva además `SelectedIcon`. */
export const COLOR_SCHEME_ICONS = {
  auto: IconDeviceDesktop,
  light: IconSun,
  dark: IconMoon,
} as const satisfies Record<string, AppIcon>;

export const SelectedIcon = IconCheck;
export const FolderIcon = IconFolder;
export const ParentFolderIcon = IconArrowUp;
export const BackIcon = IconArrowLeft;
/** Botón que contrae el menú lateral a una barra de iconos o lo despliega. */
export const NAV_RAIL_ICONS = {
  collapse: IconLayoutSidebarLeftCollapse,
  expand: IconLayoutSidebarLeftExpand,
} as const satisfies Record<string, AppIcon>;

/** Menú de acciones de una fila (2.7: usuarios). */
export const MoreActionsIcon = IconDots;
