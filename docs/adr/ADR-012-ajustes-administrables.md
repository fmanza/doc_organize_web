# ADR-012 — Ajustes administrables

- **Estado**: Aceptado (implementado en la Fase 2, 0.3.0)
- **Fecha**: 2026-10-31

## Contexto

Los ajustes de sesión, bloqueo y contraseñas (Fase 1) y los umbrales del sondeo de ubicaciones (Fase 2) son variables
`DOW_*`: cambiarlos exige editar el despliegue y reiniciar. util_bbdd_web resolvió lo mismo con su ADR-012.

## Decisión

1. Tabla `app_settings` (clave, valor JSON, quién y cuándo). **Precedencia**: valor guardado por un admin > variable
   `DOW_*` > valor por defecto. `null` borra la fila y devuelve el ajuste a la variable o al defecto.
2. **Ajustes efectivos**: copia de `Settings` con las filas aplicadas (`app/domain/settings/service.py`), que reciben las
   dependencias de la API (`SettingsDep`) y el CLI. Se leen en cada petición: **sin reiniciar**.
3. Solo claves conocidas, validadas con el tipo y el rango del campo de `Settings` (mismos límites que la variable).
   Una fila fuera de rango se ignora y se avisa en el log. **Nunca secretos** (las credenciales IA tendrán su propia
   tabla cifrada, ADR-004).
4. Claves de la Fase 2: `session_idle_minutes`, `session_absolute_hours`, `login_max_attempts`,
   `login_lockout_minutes`, `password_min_length`, `location_probe_timeout_seconds`, `location_latency_degraded_ms`,
   `location_min_free_gb`. Cuota y retención llegarán con las ejecuciones (Fase 3).
5. `GET/PATCH /api/v1/admin/settings` devuelve valor efectivo, valor sin cambio y origen (`db`/`env`/`default`); cada
   cambio se audita (`settings.update` con valor anterior y nuevo).

## Consecuencias

- Si un admin cambió un ajuste, editar la variable `DOW_*` no tiene efecto hasta restablecerlo en la web.
- `DOW_ENVIRONMENT`, rutas de volúmenes y secretos siguen siendo solo variables o Docker secrets.
