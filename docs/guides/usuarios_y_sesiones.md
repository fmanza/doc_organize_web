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

### Recuperar el acceso de administrador

Si nadie puede entrar como administrador (contraseña olvidada, cuenta bloqueada por intentos o, tras restaurar una
copia, sin ningún administrador activo), recupera una cuenta **existente** desde la línea de comandos:

```bash
docker compose exec web python -m app.cli recover-admin --username <usuario> --reset-password
```

La reactiva, quita el bloqueo, la marca como administrador de la instancia y, con `--reset-password` (o
`--password-stdin` para scripts), le pone una contraseña nueva. Cierra sus sesiones y queda en la auditoría como
«Administrador recuperado (CLI)». Si no hay ningún administrador activo, la web y el worker lo avisan en el log al
arrancar, y **Administración → Diagnóstico** lo marca como error.

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

## Tema claro u oscuro

Menú de usuario → **Tema**: **Como el sistema** (el valor por defecto: sigue el modo claro u oscuro del sistema
operativo), **Claro** u **Oscuro**. Se aplica al momento y se guarda en tu usuario, así que lo verás igual en cualquier
navegador en el que inicies sesión. El navegador guarda además una copia para pintar la pantalla de inicio de sesión con
el último tema usado en él.

El sitio entregado («6. Entregar» → «Ver el sitio») lo genera doc_organize y se ve siempre en claro.

## Idioma

Menú de usuario → **Idioma**: **Español** (el valor por defecto) o **English** (2.6). Se aplica al momento, también a
las fechas y los números (`en-GB` en inglés: día/mes/año y 24 h), y se guarda en tu usuario. El navegador guarda una
copia para mostrar el inicio de sesión en el último idioma usado en él; si no la hay, se usa el idioma del navegador
(inglés si lo prefiere, español en otro caso).

En inglés siguen en español los textos que genera el servidor:

- el detalle de los errores (el título sí se traduce);
- el mensaje de error y el registro de cada ejecución;
- las exportaciones (Excel, informes de duplicados) y el sitio del contexto, que genera doc_organize;
- los nombres de carpeta que crea doc_organize (`duplicados/`, `sitio/`) y los títulos de sección del perfil del
  proyecto (`## Contexto del proyecto`…), que son su formato.

## Administración de usuarios

**Administración → Usuarios** (con el permiso «Gestionar usuarios»), con los usuarios del tenant activo:

- **Buscar y filtrar**: el cuadro de búsqueda busca en el usuario, el nombre visible y el rol. Además puedes filtrar
  por **Rol** y por **Estado** (activo, bloqueado o bloqueado por intentos fallidos). El administrador de la
  instancia puede ver **solo los administradores de la instancia**. Los filtros quedan en la dirección de la página
  y, si no hay resultados, **Quitar filtros** los borra todos.
- **Nuevo usuario**: nombre de usuario (3 a 64 caracteres: letras, números, punto, guion o guion bajo; no distingue
  mayúsculas y es único en toda la instancia), nombre visible, rol del tenant y contraseña inicial.
- **Editar**: cambia el nombre visible o el rol, bloquea o desbloquea la cuenta y restablece la contraseña. El
  administrador de la instancia también puede marcar a otros como administradores de la instancia y moverlos de
  tenant ([Tenants y roles](tenants_y_roles.md#mover-a-un-usuario-de-tenant)).
    - **Cambiar el rol** cierra sus sesiones (los permisos nuevos valen desde que vuelva a entrar).
    - **Restablecer la contraseña** cierra sus sesiones y quita el bloqueo.
    - Si la cuenta está bloqueada por intentos fallidos, aparece **Quitar el bloqueo ahora**.
- **Más acciones** (el botón de los tres puntos de cada fila):
    - **Bloquear** impide entrar y cierra todas sus sesiones (es lo mismo que desactivar la cuenta). Puedes indicar un
      **motivo**, que solo queda en la auditoría. **Desbloquear** le deja volver a entrar y quita también el bloqueo
      por intentos fallidos.
    - **Quitar bloqueo por intentos**, si la cuenta está bloqueada temporalmente por contraseñas incorrectas.
    - **Borrar** elimina la cuenta, solo si no deja nada huérfano. Primero se comprueba y se explica qué lo impide:
      que sea tu propia cuenta, el último administrador de la instancia activo, el último gestor de usuarios del
      tenant, el **único propietario** de algún proyecto (añade otro propietario antes) o que tenga ejecuciones en cola
      o en marcha. Si se puede, se enumeran los proyectos de los que sale y las sesiones que se cierran, y hay que
      **escribir su nombre de usuario** para confirmar. No se puede deshacer. Sus ejecuciones y resultados se conservan
      sin usuario, y la auditoría guarda su nombre («ana (borrado)»).
- No puedes bloquearte, borrarte, cambiarte el rol ni quitarte ser administrador de la instancia. **Siempre queda al
  menos un administrador de la instancia activo**: al último no se le puede bloquear, quitar el rol ni borrar (sus
  acciones salen deshabilitadas, con el aviso «Debe quedar al menos un administrador activo»). Tampoco se puede dejar
  un tenant sin alguien activo que gestione sus usuarios, ni editando usuarios ni quitando el permiso a un rol.
- Solo puedes dar roles con permisos que tienes.

## Sesiones y auditoría

- **Administración → Sesiones** lista las sesiones abiertas de los usuarios del tenant; revocar una la cierra al momento.
- **Administración → Auditoría** (permiso «Consultar la auditoría») muestra los eventos del tenant activo. Registra
  inicios y cierres de sesión (también los fallidos), bloqueos, cambios de contraseña, altas, ediciones,
  desactivaciones y desbloqueos de usuarios y sesiones revocadas, y también los cambios en roles, tenants, ubicaciones,
  ajustes, IA y proyectos (miembros, carpetas, operaciones que mueven o borran, contexto), con fecha, autor e IP. Se
  puede buscar y filtrar por tipo de acción (Autenticación, Usuarios, Sesiones) y por usuario que actuó. Nunca se
  guardan contraseñas.
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
- Desde la 1.5.0, cada documento muestra debajo su tipo (MIME), la fecha de creación y los permisos, cuando el
  sistema de ficheros los da. Desde la 1.6, se puede **filtrar por tipo de fichero** (uno o varios; el desplegable dice
  cuántos documentos hay de cada uno) y **ordenar por tipo o por fecha de creación**. Los que no tienen el dato van al
  final. Los owners del proyecto pueden ordenar también por **propietario** (sin distinguir mayúsculas); al resto la
  API se lo niega, porque el orden dejaría deducir de quién es cada fichero.

### Propietario de los ficheros

El owner del proyecto puede activar «Guardar el propietario de cada fichero» en **Editar** (desactivado por
defecto). Es un dato personal:

- Solo lo ven los owners del proyecto y los administradores.
- Se aplica desde el siguiente escaneo, y el cambio queda en la auditoría.
- Al desactivarlo, el siguiente escaneo lo borra de la caché.
