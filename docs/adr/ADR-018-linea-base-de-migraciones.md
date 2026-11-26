# ADR-018 — Línea base de migraciones y versiones desde las que se actualiza

- **Estado**: Aceptado (web 3.0.0)
- **Fecha**: 2026-11-26
- **Sustituye**: la cadena de migraciones `0001`–`0033` de la 1.x y la 2.x

## Contexto

Hasta la 2.8 la `config.db` se creaba aplicando 33 migraciones de Alembic. Nueve de ellas movían datos (familias de IA
de la 1.x, taxonomía por ejes, ubicaciones de proyectos borrados…) y la `0017` importaba código de la aplicación. Esa
cadena:

- tarda en crear cada BD nueva, en producción y en los tests;
- obliga a mantener código de migraciones de datos que ya no tiene a quién aplicarse;
- fija dependencias de las migraciones con la aplicación de entonces;
- emite el DDL de las tablas recreadas en *batch* en un orden que depende de `PYTHONHASHSEED`.

La 3.0 es una versión mayor que ya exige intervenir al actualizar (`docs/plan/VERSION_3.0.md`).

## Decisión

1. **Una sola migración inicial, la línea base `0033_baseline.py`**, con la revisión **`0033`** y sin padre. Crea el
   esquema y las filas semilla (el tenant `default` y sus roles base) que dejaba la cadena en `0033`.
2. **El DDL se copia literal** de `backend/tests/fixtures/schema_0033.sql`, el volcado de la BD que dejaba la cadena,
   con las restricciones de tabla ordenadas. No se genera desde los modelos, porque las tablas recreadas en *batch* no
   coinciden con `create_all`. La línea base no importa nada de `app`.
3. **Se conserva el id `0033`**: una `config.db` de la 2.7.x o la 2.8.x ya está en la línea base y `alembic upgrade head`
   solo aplica lo posterior.
4. **Puerta de versión** (`app/db/migrations.py`, llamada desde `alembic/env.py`): si la BD tiene una revisión que no
   está en `alembic/versions`, la migración falla con `UnsupportedRevisionError` y un mensaje que pide pasar antes por
   la 2.8.x. El mensaje no muestra la ruta de la BD. Como `docker/entrypoint.sh` migra antes de arrancar, el contenedor
   se para con ese mensaje.
5. **Pruebas**:
    - `test_0033_matches_the_schema_snapshot`: la línea base deja exactamente el snapshot;
    - `test_the_chain_starts_at_the_0033_baseline` y `test_a_2_8_database_is_already_at_the_baseline`;
    - `test_a_database_older_than_2_7_is_rejected_without_its_path`.

    Las pruebas de cada migración de datos antigua se retiran con ellas.

## Consecuencias

- Solo se actualiza a la 3.0 desde la 2.7.x o la 2.8.x. Desde una versión anterior hay que instalar antes la 2.8.x y
  arrancarla una vez.
- `alembic downgrade` no baja de `0033`. Para volver a una versión anterior a la 2.7 se restaura una copia.
- Crear una BD nueva es mucho más rápido: los tests de migraciones pasan de minutos a segundos.
- Las migraciones nuevas de la 3.x se numeran desde `3001` y parten de `0033`.
- `scripts/migration_roundtrip.py` sigue sirviendo para probar la ida y vuelta de las migraciones posteriores a la
  línea base sobre una copia.
