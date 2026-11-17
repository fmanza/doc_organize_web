import { ICON_STROKE, SMALL_ICON_SIZE, type AppIcon } from './icons';

/** Pinta un icono de `icons.ts` como decoración: oculto para los lectores de pantalla y sin foco. */
export function Icon({ of: Component, size = SMALL_ICON_SIZE }: { of: AppIcon; size?: number }) {
  return <Component size={size} stroke={ICON_STROKE} aria-hidden="true" focusable="false" />;
}
