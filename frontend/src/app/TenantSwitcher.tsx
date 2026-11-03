import { Badge, Select } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../components/ErrorAlert';
import { useSwitchTenant, useTenants } from '../features/admin/useTenancy';
import { useMe } from '../features/auth/useAuth';

/**
 * Tenant activo en la cabecera (Fase 9): el admin de instancia elige en cuál actúa (decisión E2: va en la sesión);
 * el resto ve el nombre de su tenant solo si hay más de uno (la API no les deja listarlos: se muestra siempre).
 */
export function TenantSwitcher() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const instance = !!me?.is_instance_admin;
  const tenants = useTenants(instance);
  const switchTenant = useSwitchTenant();

  if (!me) {
    return null;
  }
  if (!instance) {
    return (
      <Badge variant="light" color="gray" aria-label={t('tenants.current', { name: me.tenant.name })}>
        {me.tenant.name}
      </Badge>
    );
  }
  return (
    <>
      <Select
        aria-label={t('tenants.switch')}
        size="xs"
        w={200}
        data={(tenants.data?.items ?? [me.acting_tenant]).map((tenant) => ({
          value: String(tenant.id),
          label: tenant.name,
        }))}
        value={String(me.acting_tenant.id)}
        onChange={(value) =>
          value && switchTenant.mutate(Number(value) === me.tenant.id ? null : Number(value))
        }
        allowDeselect={false}
        disabled={switchTenant.isPending}
        comboboxProps={{ withinPortal: true }}
      />
      {switchTenant.isError && <ErrorAlert error={switchTenant.error} />}
    </>
  );
}
