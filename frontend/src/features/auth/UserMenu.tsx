import { Badge, Button, Menu } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { useLogout, useMe } from './useAuth';

export function UserMenu() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const logout = useLogout();
  const [permission, setPermission] = useState(() =>
    typeof window.Notification === 'undefined' ? 'denied' : window.Notification.permission,
  );

  if (!me) {
    return null;
  }

  const onLogout = () => {
    logout.mutate(undefined, { onSettled: () => void navigate('/login', { replace: true }) });
  };

  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Button
          variant="subtle"
          rightSection={
            me.is_instance_admin ? (
              <Badge size="xs" variant="light">
                {t('roles.instanceAdmin')}
              </Badge>
            ) : undefined
          }
          aria-label={t('auth.userMenu', { name: me.display_name })}
        >
          {me.display_name}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>
          {me.username} · {me.tenant.name}
        </Menu.Label>
        <Menu.Item component={Link} to="/account/password">
          {t('auth.changePassword')}
        </Menu.Item>
        <Menu.Item component={Link} to="/account/sessions">
          {t('auth.mySessions')}
        </Menu.Item>
        {permission === 'default' && (
          // M2: el permiso solo se pide al pulsar (los navegadores lo exigen y es lo que espera el usuario).
          <Menu.Item onClick={() => void window.Notification.requestPermission().then(setPermission)}>
            {t('runs.notify.enable')}
          </Menu.Item>
        )}
        <Menu.Item onClick={onLogout} disabled={logout.isPending}>
          {t('auth.logout')}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}
