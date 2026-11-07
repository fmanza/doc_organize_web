import {
  Anchor,
  Badge,
  Breadcrumbs,
  Button,
  Center,
  Checkbox,
  Group,
  Loader,
  NavLink,
  Pagination,
  Stack,
  Text,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { FOLDER_PAGE_SIZE, useFolders } from '../features/locations/useLocations';
import { ErrorAlert } from './ErrorAlert';

interface FolderBrowserProps {
  /** Ubicación a explorar; `null` explora la raíz de montajes (`/mnt`, solo admin). */
  locationId: number | null;
  /** Nombre que se muestra como primera miga (la raíz). */
  rootLabel: string;
  /** Si se indica, aparece «Elegir esta carpeta» con la ruta relativa actual. */
  onSelect?: (path: string) => void;
  /** Ruta relativa seleccionada, para resaltarla (``''`` es la raíz de la ubicación). */
  selected?: string | undefined;
  /** Si la raíz de la ubicación se puede elegir; si no, «Elegir esta carpeta» se desactiva en ella y se explica. */
  rootSelectable?: boolean;
  /** Por qué no se puede elegir la raíz (solo con ``rootSelectable={false}``). */
  rootHint?: string;
  /** Carpeta de partida y tope (relativa a la ubicación): no se sube por encima y la primera miga es ella. */
  basePath?: string;
  /** Casilla en cada subcarpeta (rutas relativas a la ubicación); lo marcado sale tachado con `checkedTag`. */
  checkable?: FolderCheckable;
}

export interface FolderCheckable {
  checked: ReadonlySet<string>;
  onChange: (path: string, checked: boolean) => void;
  /** Nombre accesible de la casilla de una subcarpeta. */
  label: (name: string) => string;
  /** Etiqueta de lo marcado (o de lo que está dentro de algo marcado). */
  checkedTag: string;
}

function within(path: string, parent: string): boolean {
  return path.startsWith(`${parent}/`);
}

/**
 * Explorador de carpetas reutilizable (sustituye a `_folder_browser_macros`): solo rutas relativas a la ubicación,
 * migas para subir, lista paginada en servidor y estados de carga, vacío, error y ubicación no disponible (503).
 */
export function FolderBrowser({
  locationId,
  rootLabel,
  onSelect,
  selected,
  rootSelectable = true,
  rootHint,
  basePath = '',
  checkable,
}: FolderBrowserProps) {
  const { t } = useTranslation();
  const [path, setPath] = useState(basePath);
  const [page, setPage] = useState(1);
  const { data, isPending, isError, error, isFetching } = useFolders(locationId, path, page);

  const go = (next: string) => {
    setPath(basePath && next !== basePath && !within(next, basePath) ? basePath : next);
    setPage(1);
  };
  const relative = basePath ? path.slice(basePath.length).replace(/^\//, '') : path;
  const crumbs = relative ? relative.split('/') : [];
  const crumbPath = (index: number) =>
    [basePath, ...crumbs.slice(0, index + 1)].filter((part) => part !== '').join('/');
  const blocked = !rootSelectable && path === '';
  const covered = (item: string) => [...(checkable?.checked ?? [])].some((c) => within(item, c));

  return (
    <Stack gap="sm">
      <Breadcrumbs aria-label={t('folders.breadcrumbs')}>
        <Anchor component="button" type="button" onClick={() => go(basePath)}>
          {rootLabel}
        </Anchor>
        {crumbs.map((name, index) => (
          <Anchor
            key={crumbPath(index)}
            component="button"
            type="button"
            onClick={() => go(crumbPath(index))}
            aria-current={index === crumbs.length - 1 ? 'location' : undefined}
          >
            {name}
          </Anchor>
        ))}
      </Breadcrumbs>
      {onSelect && (
        <Stack gap={4}>
          <Group>
            <Button
              size="xs"
              onClick={() => onSelect(path)}
              variant={selected === path ? 'filled' : 'light'}
              disabled={blocked}
            >
              {t('folders.select')}
            </Button>
            <Text size="sm" c="dimmed">
              {selected === undefined || (selected === '' && !rootSelectable)
                ? t('folders.nothingSelected')
                : selected === ''
                  ? t('folders.selectedRoot', { name: rootLabel })
                  : t('folders.selected', { path: selected })}
            </Text>
          </Group>
          {blocked && rootHint && (
            <Text size="xs" c="orange">
              {rootHint}
            </Text>
          )}
        </Stack>
      )}
      {isPending && (
        <Center>
          <Loader size="sm" aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && (
        <Stack gap={2} role="group" aria-busy={isFetching} aria-label={t('folders.list')}>
          {data.parent !== null && path !== basePath && (
            <NavLink
              component="button"
              type="button"
              label={t('folders.up')}
              leftSection={<span aria-hidden="true">↑</span>}
              onClick={() => go(data.parent ?? '')}
            />
          )}
          {data.items.length === 0 && (
            <Text size="sm" c="dimmed">
              {locationId === null && path === '' ? t('folders.emptyMounts') : t('folders.empty')}
            </Text>
          )}
          {data.items.map((item) => {
            const link = (
              <NavLink
                key={item.path}
                component="button"
                type="button"
                label={item.name}
                leftSection={<span aria-hidden="true">📁</span>}
                onClick={() => go(item.path)}
              />
            );
            if (!checkable) {
              return link;
            }
            const inherited = covered(item.path);
            const marked = inherited || checkable.checked.has(item.path);
            return (
              <Group key={item.path} gap="xs" wrap="nowrap">
                <Checkbox
                  aria-label={checkable.label(item.name)}
                  checked={marked}
                  disabled={inherited}
                  onChange={(event) => checkable.onChange(item.path, event.currentTarget.checked)}
                />
                <NavLink
                  component="button"
                  type="button"
                  label={
                    <Group gap="xs" wrap="nowrap">
                      <Text span size="sm" td={marked ? 'line-through' : undefined}>
                        {item.name}
                      </Text>
                      {marked && (
                        <Badge size="sm" color="gray" variant="light">
                          {checkable.checkedTag}
                        </Badge>
                      )}
                    </Group>
                  }
                  leftSection={<span aria-hidden="true">📁</span>}
                  onClick={() => go(item.path)}
                />
              </Group>
            );
          })}
          {data.total > FOLDER_PAGE_SIZE && (
            <Pagination
              mt="xs"
              total={Math.ceil(data.total / FOLDER_PAGE_SIZE)}
              value={page}
              onChange={setPage}
              size="sm"
            />
          )}
        </Stack>
      )}
    </Stack>
  );
}
