import type { paths } from './schema';

type GetQuery<P extends keyof paths> = paths[P] extends { get: { parameters: { query?: infer Q } } }
  ? NonNullable<Q>
  : never;

/** Claves de orden que admite el listado `P` (el `Literal` de `sort` en la API, web 1.2.0). */
export type SortOf<P extends keyof paths> =
  GetQuery<P> extends { sort?: infer S } ? Exclude<S, null | undefined> : never;

/** Página, búsqueda y orden que se mandan a un listado (lo que devuelve `useListState(...).query`). */
export interface ListParams<K extends string = string> {
  limit: number;
  offset: number;
  q?: string;
  sort?: K;
  order?: 'asc' | 'desc';
}
