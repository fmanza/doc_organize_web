import type { NavIconKey } from '../components/icons';
import { can, type Me, type Permission } from '../features/auth/useAuth';

/** Página de administración con lo que exige (las mismas guardas que el router). */
export interface AdminPage {
  /** Clave de `nav.<clave>` y de `NAV_ICONS`: cada página tiene su icono por construcción. */
  key: NavIconKey;
  to: string;
  permission?: Permission;
  instance?: boolean;
}

/** Entrada del menú de administración: una página o un grupo de páginas (W1). */
export type AdminEntry = AdminPage | { group: NavIconKey; pages: AdminPage[] };

const ADMIN_MENU: AdminEntry[] = [
  {
    group: 'access',
    pages: [
      { key: 'users', to: '/admin/users', permission: 'users.manage' },
      { key: 'roles', to: '/admin/roles', permission: 'roles.manage' },
      { key: 'sessions', to: '/admin/sessions', permission: 'users.manage' },
      { key: 'tenants', to: '/admin/tenants', instance: true },
    ],
  },
  { key: 'taxonomy-templates', to: '/admin/taxonomy-templates', permission: 'templates.manage' },
  {
    group: 'ai',
    pages: [
      { key: 'ai-settings', to: '/admin/ai/settings', instance: true },
      { key: 'ai-parameters', to: '/admin/ai/parameters', instance: true },
      { key: 'ai-usage', to: '/admin/ai/usage', instance: true },
    ],
  },
  { key: 'settings', to: '/admin/settings', instance: true },
  { key: 'info', to: '/admin/info', instance: true },
  { key: 'audit', to: '/admin/audit', permission: 'audit.read' },
];

/**
 * Menú de administración que ve `me`: cada página con su guarda, y un grupo solo si le queda alguna página (un
 * administrador de tenant no ve un «IA» vacío).
 */
export function visibleAdminMenu(me: Me | null | undefined): AdminEntry[] {
  const allowed = (page: AdminPage) =>
    page.instance ? Boolean(me?.is_instance_admin) : page.permission ? can(me, page.permission) : false;
  return ADMIN_MENU.flatMap((entry): AdminEntry[] => {
    if ('group' in entry) {
      const pages = entry.pages.filter(allowed);
      return pages.length > 0 ? [{ group: entry.group, pages }] : [];
    }
    return allowed(entry) ? [entry] : [];
  });
}
