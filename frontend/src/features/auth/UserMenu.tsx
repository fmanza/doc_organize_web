import { Badge, Button, Menu } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { useLogout, useMe } from './useAuth';

export function UserMenu() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const logout = useLogout();

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
            me.role === 'admin' ? (
              <Badge size="xs" variant="light">
                {t('roles.admin')}
              </Badge>
            ) : undefined
          }
          aria-label={t('auth.userMenu', { name: me.display_name })}
        >
          {me.display_name}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{me.username}</Menu.Label>
        <Menu.Item component={Link} to="/account/password">
          {t('auth.changePassword')}
        </Menu.Item>
        <Menu.Item component={Link} to="/account/sessions">
          {t('auth.mySessions')}
        </Menu.Item>
        <Menu.Item onClick={onLogout} disabled={logout.isPending}>
          {t('auth.logout')}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}
