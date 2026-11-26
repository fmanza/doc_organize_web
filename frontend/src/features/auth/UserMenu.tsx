import { Avatar, Badge, Button, Group, Menu } from '@mantine/core';
import { Fragment, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { COLOR_SCHEMES } from '../../app/colorScheme';
import { ICON_STROKE, COLOR_SCHEME_ICONS, NAV_ICON_SIZE, SelectedIcon } from '../../components/icons';
import { ToastStack } from '../../components/Toasts';
import { useToasts } from '../../components/useToasts';
import { LANGUAGES, type Language } from '../../i18n';
import { type ColorScheme, useLogout, useMe, useUpdateColorScheme, useUpdateLanguage } from './useAuth';

export function UserMenu() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const logout = useLogout();
  const updateScheme = useUpdateColorScheme();
  const updateLanguage = useUpdateLanguage();
  const { toasts, push, dismiss } = useToasts();
  const [permission, setPermission] = useState(() =>
    typeof window.Notification === 'undefined' ? 'denied' : window.Notification.permission,
  );

  if (!me) {
    return null;
  }

  const chooseScheme = (scheme: ColorScheme) => {
    if (scheme === me.color_scheme) {
      return;
    }
    updateScheme.mutate(scheme, {
      onError: () => push({ color: 'red', title: t('auth.colorScheme.saveFailed') }),
    });
  };

  const chooseLanguage = (language: Language) => {
    if (language === me.language) {
      return;
    }
    updateLanguage.mutate(language, {
      onError: () => push({ color: 'red', title: t('auth.language.saveFailed') }),
    });
  };

  const adminBadge = me.is_instance_admin ? (
    <Badge size="xs" variant="light">
      {t('roles.instanceAdmin')}
    </Badge>
  ) : null;

  const onLogout = () => {
    logout.mutate(undefined, { onSettled: () => void navigate('/login', { replace: true }) });
  };

  return (
    <Fragment>
      <ToastStack toasts={toasts} onClose={dismiss} />
      <Menu position="bottom-end" withinPortal>
        <Menu.Target>
          {/* Por debajo de `sm`, solo las iniciales; el nombre y el rol pasan al desplegable. */}
          <Button
            variant="subtle"
            px={{ base: 4, sm: 'sm' }}
            aria-label={t('auth.userMenu', { name: me.display_name })}
          >
            <Avatar
              hiddenFrom="sm"
              size={28}
              radius="xl"
              color="initials"
              name={me.display_name}
              aria-hidden
            />
            <Group gap={8} wrap="nowrap" visibleFrom="sm">
              {me.display_name}
              {adminBadge}
            </Group>
          </Button>
        </Menu.Target>
        <Menu.Dropdown>
          <Group hiddenFrom="sm" gap={8} px="sm" py={6} wrap="nowrap">
            {me.display_name}
            {adminBadge}
          </Group>
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
          <Menu.Divider />
          {/* 2.3: el tema se guarda en el usuario; el menú sigue abierto para ver el cambio. */}
          <div role="group" aria-label={t('auth.colorScheme.label')}>
            <Menu.Label>{t('auth.colorScheme.label')}</Menu.Label>
            {COLOR_SCHEMES.map((scheme) => {
              const Icon = COLOR_SCHEME_ICONS[scheme];
              const selected = me.color_scheme === scheme;
              return (
                <Menu.Item
                  key={scheme}
                  // Mantine fija role="menuitem" (no admite menuitemradio/aria-checked): la elegida lleva aria-current.
                  aria-current={selected ? 'true' : undefined}
                  closeMenuOnClick={false}
                  onClick={() => chooseScheme(scheme)}
                  leftSection={<Icon size={NAV_ICON_SIZE} stroke={ICON_STROKE} aria-hidden />}
                  rightSection={
                    selected ? <SelectedIcon size={NAV_ICON_SIZE} stroke={ICON_STROKE} aria-hidden /> : null
                  }
                >
                  {t(`auth.colorScheme.${scheme}`)}
                </Menu.Item>
              );
            })}
          </div>
          <Menu.Divider />
          {/* 2.6: el idioma se guarda en el usuario; cada idioma se nombra en su idioma (con su `lang`). */}
          <div role="group" aria-label={t('auth.language.label')}>
            <Menu.Label>{t('auth.language.label')}</Menu.Label>
            {LANGUAGES.map((language) => {
              const selected = me.language === language;
              return (
                <Menu.Item
                  key={language}
                  lang={language}
                  aria-current={selected ? 'true' : undefined}
                  closeMenuOnClick={false}
                  onClick={() => chooseLanguage(language)}
                  rightSection={
                    selected ? <SelectedIcon size={NAV_ICON_SIZE} stroke={ICON_STROKE} aria-hidden /> : null
                  }
                >
                  {t(`auth.language.${language}`)}
                </Menu.Item>
              );
            })}
          </div>
          <Menu.Divider />
          <Menu.Item onClick={onLogout} disabled={logout.isPending}>
            {t('auth.logout')}
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
    </Fragment>
  );
}
