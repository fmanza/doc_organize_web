import { Badge, Button, Group, NumberInput, Table, Text } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { type SettingOut, useUpdateSettings } from './useSettings';

function SettingRow({ setting, usedIn }: { setting: SettingOut; usedIn?: readonly string[] | undefined }) {
  const { t } = useTranslation();
  const update = useUpdateSettings();
  const [value, setValue] = useState<string | number>(setting.value);
  const label = t(`settings.keys.${setting.key}.label`);
  const dirty = Number(value) !== setting.value;

  return (
    <Table.Tr>
      <Table.Td>
        <Text fw={500}>{label}</Text>
        <Text size="xs" c="dimmed">
          {t(`settings.keys.${setting.key}.hint`)}
        </Text>
        {usedIn && usedIn.length > 0 && (
          <Group gap={4} mt={4} aria-label={t('settings.usedInLabel', { label })}>
            <Text size="xs" c="dimmed">
              {t('settings.usedIn')}
            </Text>
            {usedIn.map((feature) => (
              <Badge key={feature} size="xs" variant="outline" color="gray">
                {feature}
              </Badge>
            ))}
          </Group>
        )}
        {update.isError && <ErrorAlert error={update.error} mt="xs" />}
      </Table.Td>
      <Table.Td>
        <NumberInput
          aria-label={label}
          value={value}
          onChange={setValue}
          allowDecimal={false}
          min={0}
          w={130}
        />
      </Table.Td>
      <Table.Td>
        <Badge variant="light" color={setting.source === 'db' ? 'blue' : 'gray'}>
          {t(`settings.source.${setting.source}`)}
        </Badge>
        {setting.source === 'db' && (
          <Text size="xs" c="dimmed">
            {t('settings.defaultIs', { value: setting.default })}
          </Text>
        )}
      </Table.Td>
      <Table.Td>
        <Group gap="xs" wrap="nowrap">
          <Button
            size="xs"
            disabled={!dirty || value === ''}
            loading={update.isPending}
            onClick={() => update.mutate({ [setting.key]: Number(value) })}
            aria-label={t('settings.saveLabel', { label })}
          >
            {t('common.save')}
          </Button>
          {setting.source === 'db' && (
            <Button
              size="xs"
              variant="default"
              loading={update.isPending}
              onClick={() =>
                update.mutate({ [setting.key]: null }, { onSuccess: () => setValue(setting.default) })
              }
              aria-label={t('settings.resetLabel', { label })}
            >
              {t('settings.reset')}
            </Button>
          )}
        </Group>
      </Table.Td>
    </Table.Tr>
  );
}

/**
 * Tabla de ajustes administrables (ADR-012): la usan «Ajustes» (una por sección) e «IA › Parámetros». Todos se guardan
 * con el mismo `PATCH /admin/settings`, con su validación y su auditoría. `usedIn` (2.2): clave → funcionalidades que
 * usan ese ajuste, para decirlo junto a cada uno.
 */
export function SettingsTable({
  settings,
  usedIn,
}: {
  settings: SettingOut[];
  usedIn?: Readonly<Record<string, readonly string[]>>;
}) {
  const { t } = useTranslation();
  return (
    <Table.ScrollContainer minWidth={760}>
      {/*
        Anchos fijos: cada sección de «Ajustes» es una tabla, y con anchos automáticos sus columnas no coincidían de
        una a otra. Así todas se alinean con la primera («Sesión e inicio de sesión») y el texto del ajuste se lleva
        el ancho que sobre.
      */}
      <Table layout="fixed">
        <colgroup>
          <col />
          <col style={{ width: 160 }} />
          <col style={{ width: 190 }} />
          <col style={{ width: 210 }} />
        </colgroup>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('settings.setting')}</Table.Th>
            <Table.Th>{t('settings.value')}</Table.Th>
            <Table.Th>{t('settings.origin')}</Table.Th>
            <Table.Th>{t('common.actions')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {settings.map((setting) => (
            <SettingRow
              key={`${setting.key}-${setting.value}`}
              setting={setting}
              usedIn={usedIn?.[setting.key]}
            />
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
