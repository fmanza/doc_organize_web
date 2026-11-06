# Usuarios y sesiones

Desde la 0.2.0 la aplicación exige iniciar sesión. Cada usuario pertenece a un **tenant** (organización) y tiene un
**rol** de ese tenant; el **administrador de la instancia** gestiona lo que es del servidor. Ver
[Tenants y roles](tenants_y_roles.md).

## Primer administrador

No hay credenciales por defecto. El primer administrador de la instancia (con el rol «Administrador» del tenant
predeterminado) se crea por línea de comandos, con la aplicación en marcha:

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

**Administración → Usuarios** (con el permiso «Gestionar usuarios»), con los usuarios del tenant activo:

- **Nuevo usuario**: nombre de usuario (3 a 64 caracteres: letras, números, punto, guion o guion bajo; no distingue
  mayúsculas y es único en toda la instancia), nombre visible, rol del tenant y contraseña inicial.
- **Editar**: cambia el nombre visible o el rol, desactiva o reactiva la cuenta y restablece la contraseña. El
  administrador de la instancia también puede marcar a otros como administradores de la instancia y moverlos de
  tenant ([Tenants y roles](tenants_y_roles.md#mover-a-un-usuario-de-tenant)).
    - **Cambiar el rol** cierra sus sesiones (los permisos nuevos valen desde que vuelva a entrar).
    - **Desactivar** cierra todas sus sesiones. Los usuarios **no se borran**: así la auditoría conserva quién hizo
      cada cosa.
    - **Restablecer la contraseña** cierra sus sesiones y quita el bloqueo.
    - Si la cuenta está bloqueada por intentos fallidos, aparece **Quitar el bloqueo ahora**.
- No puedes desactivarte, cambiarte el rol ni quitarte ser administrador de la instancia. Siempre queda al menos un
  administrador de la instancia activo y, en cada tenant, alguien activo que gestione sus usuarios.
- Solo puedes dar roles con permisos que tienes.

## Sesiones y auditoría

- **Administración → Sesiones** lista las sesiones abiertas de los usuarios del tenant; revocar una la cierra al momento.
- **Administración → Auditoría** (permiso «Consultar la auditoría») muestra los eventos del tenant activo. Registra inicios y cierres de sesión (también los fallidos), bloqueos, cambios de
  contraseña, altas, ediciones, desactivaciones y desbloqueos de usuarios, y sesiones revocadas, con fecha, autor e IP.
  Se puede filtrar por tipo de acción y por usuario que actuó. Nunca se guardan contraseñas.
- **Eliminar auditoría por fechas** (solo el **administrador de la instancia**): botón «Eliminar por fechas» de
  Administración → Auditoría. Borra para siempre las entradas del **tenant activo** entre dos fechas (UTC).
  1. Elige «Desde» (incluido) y «Hasta» (sin incluir). «Hasta» no puede pasar de hoy: las entradas de hoy no se
     borran nunca, para que no se pueda tapar lo que acaba de pasar.
  2. «Comprobar» dice cuántas entradas hay en ese rango.
  3. Para borrar, escribe ese número. Si entretanto ha cambiado, la aplicación lo dice y hay que volver a
     comprobar.

  El borrado queda registrado en la propia auditoría (`audit.purge`, con el rango y el número de entradas). Las
  copias de seguridad anteriores siguen teniendo las entradas borradas.

## Listados

Todos los listados de la aplicación funcionan igual (desde la 1.2.0):

- **25 filas por página** como mucho, con la página en la dirección: se puede compartir y «Atrás» vuelve a ella.
- **Buscar**: el cuadro de búsqueda filtra por el texto de las columnas principales (sin distinguir mayúsculas).
- **Ordenar**: pulsa el título de una columna; otra vez, para invertir el orden. La flecha indica la columna y el
  sentido. Los grupos de duplicados, que son tarjetas, tienen un selector «Ordenar por».
- Los **documentos** del proyecto se ordenan con «Ordenar por» (ruta, última actualización, estado de conversión o
  fallos seguidos) desde la 1.3.0. Sin elegir nada, salen por carpeta y ruta.
