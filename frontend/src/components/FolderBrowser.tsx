import {
  Anchor,
  Breadcrumbs,
  Button,
  Center,
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
}: FolderBrowserProps) {
  const { t } = useTranslation();
  const [path, setPath] = useState('');
  const [page, setPage] = useState(1);
  const { data, isPending, isError, error, isFetching } = useFolders(locationId, path, page);

  const go = (next: string) => {
    setPath(next);
    setPage(1);
  };
  const crumbs = path ? path.split('/') : [];
  const blocked = !rootSelectable && path === '';

  return (
    <Stack gap="sm">
      <Breadcrumbs aria-label={t('folders.breadcrumbs')}>
        <Anchor component="button" type="button" onClick={() => go('')}>
          {rootLabel}
        </Anchor>
        {crumbs.map((name, index) => (
          <Anchor
            key={crumbs.slice(0, index + 1).join('/')}
            component="button"
            type="button"
            onClick={() => go(crumbs.slice(0, index + 1).join('/'))}
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
          {data.parent !== null && (
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
          {data.items.map((item) => (
            <NavLink
              key={item.path}
              component="button"
              type="button"
              label={item.name}
              leftSection={<span aria-hidden="true">📁</span>}
              onClick={() => go(item.path)}
            />
          ))}
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
