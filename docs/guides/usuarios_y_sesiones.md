# Usuarios y sesiones

Desde la 0.2.0 la aplicación exige iniciar sesión. Hay dos roles: **administrador** (gestiona usuarios, sesiones y
auditoría) y **usuario**. Los roles personalizados y las organizaciones (*tenants*) llegan en la Fase 9.

## Primer administrador

No hay credenciales por defecto. El primer administrador se crea por línea de comandos, con la aplicación en marcha:

```bash
docker compose exec web python -m app.cli create-admin --username <usuario>
```

La contraseña se pide dos veces por el terminal. Para scripts, `--password-stdin` la lee de la entrada estándar (nunca
la pases como argumento: quedaría en el historial del shell).

## Iniciar y cerrar sesión

- Entra en la aplicación con tu usuario y contraseña. Si el usuario no existe, está desactivado o bloqueado, o la
  contraseña es incorrecta, el mensaje es el mismo («Credenciales no válidas»): así no se puede averiguar qué usuarios
  existen.
- Tras **5 intentos fallidos seguidos** la cuenta se bloquea **15 minutos**. Un administrador puede quitar el bloqueo
  antes.
- La sesión se cierra sola tras **60 minutos sin actividad** o **12 horas** desde que la abriste. Cierra sesión desde el
  menú de usuario (arriba a la derecha).

Los valores entre negritas son los de por defecto; el administrador del servidor puede cambiarlos
([despliegue](despliegue.md#variables)).

## Cambiar tu contraseña

Menú de usuario → **Cambiar contraseña**. La nueva debe tener al menos 12 caracteres, no coincidir con tu nombre de
usuario y no ser una de las contraseñas más habituales (tampoco con números o símbolos añadidos: `Password1234!` se
rechaza). Mejor una frase larga que una palabra rebuscada. Al cambiarla se cierran tus sesiones en otros navegadores.

## Mis sesiones

Menú de usuario → **Mis sesiones** muestra dónde tienes la sesión abierta (IP, navegador, inicio y última actividad).
Puedes revocar cualquiera; si revocas la actual, vuelves al inicio de sesión.

## Administración de usuarios

**Administración → Usuarios** (solo administradores):

- **Nuevo usuario**: nombre de usuario (3 a 64 caracteres: letras, números, punto, guion o guion bajo; no distingue
  mayúsculas), nombre visible, rol y contraseña inicial.
- **Editar**: cambia el nombre visible o el rol, desactiva o reactiva la cuenta y restablece la contraseña.
    - **Desactivar** cierra todas sus sesiones. Los usuarios **no se borran**: así la auditoría conserva quién hizo
      cada cosa.
    - **Restablecer la contraseña** cierra sus sesiones y quita el bloqueo.
    - Si la cuenta está bloqueada por intentos fallidos, aparece **Quitar el bloqueo ahora**.
- No puedes desactivarte ni quitarte el rol de administrador, y siempre debe quedar al menos un administrador activo.

## Sesiones y auditoría

- **Administración → Sesiones** lista las sesiones abiertas de todos los usuarios; revocar una la cierra al momento.
- **Administración → Auditoría** registra inicios y cierres de sesión (también los fallidos), bloqueos, cambios de
  contraseña, altas, ediciones, desactivaciones y desbloqueos de usuarios, y sesiones revocadas, con fecha, autor e IP.
  Se puede filtrar por tipo de acción y por usuario que actuó. Nunca se guardan contraseñas.
