# Tenants y roles

Un **tenant** es una organización aislada. Tiene sus propios usuarios, roles, proyectos, ubicaciones, plantillas de
taxonomía y auditoría. Lo de un tenant es invisible para los demás: si alguien pide un recurso de otro tenant, la
aplicación responde como si no existiera. La instalación empieza con un tenant, **Predeterminado**.

## Quién gestiona qué

| Quién | Qué gestiona |
|---|---|
| **Administrador de la instancia** | Tenants, ubicaciones (también a qué tenant pertenece cada una), ajustes, [IA](ia.md), workers y capacidades. Tiene todos los permisos en cualquier tenant |
| **Rol del tenant** | Lo que dicen sus permisos, solo dentro de su tenant |
| **Miembros de cada proyecto** | El proyecto: propietario, editor o lector ([Proyectos](proyectos.md)) |

El primer administrador de la instancia se crea por línea de comandos ([Usuarios y sesiones](usuarios_y_sesiones.md)).
Los administradores de la versión 0.9.0 pasan a serlo de la instancia, con el rol «Administrador» del tenant
predeterminado, y los usuarios pasan al rol «Usuario».

## Tenants (administrador de la instancia)

**Administración → Tenants** lista los tenants con sus usuarios, proyectos y ubicaciones:

- **Nuevo tenant**: identificador (minúsculas, dígitos y guiones; no se puede cambiar) y nombre. Se crea con sus dos
  roles base.
- **Renombrar** cambia el nombre visible.
- **Borrar** solo funciona con un tenant vacío: sin usuarios (tampoco desactivados), proyectos (tampoco borrados),
  ubicaciones ni plantillas. No hay borrado en cascada. Su auditoría pasa al tenant predeterminado. El tenant
  predeterminado no se borra.

### Actuar en otro tenant

El administrador de la instancia elige en la cabecera el **tenant activo**, o pulsa **Actuar en él** en la lista.
Desde ese momento, todo lo que ve y hace en esa sesión es de ese tenant: proyectos, ubicaciones, usuarios, roles,
plantillas y auditoría. El cambio queda en la auditoría. El resto de usuarios ve en la cabecera el nombre de su
tenant.

### Mover a un usuario de tenant

Solo lo hace el administrador de la instancia, desde **Editar usuario → Tenant**. Al moverlo:

- deja de ser miembro de los proyectos del tenant anterior;
- pasa al rol «Usuario» del tenant nuevo;
- se cierran sus sesiones.

Queda en la auditoría con cuántas membresías perdió.

## Roles (permiso «Gestionar roles»)

**Administración → Roles** funciona como la lista de usuarios (desde la 1.2.0):

- un **listado** con el nombre, el tipo, los permisos, cuántos usuarios tiene y cuándo se modificó, con búsqueda,
  orden por columna y 25 filas por página;
- el botón **Nuevo rol**, que abre el formulario;
- en cada fila, **Editar**. Los roles base salen marcados como **Predeterminado** y su botón es **Ver**: se
  abren en solo lectura.

Los permisos que se pueden dar son:

| Permiso | Qué permite |
|---|---|
| Gestionar usuarios | Alta, edición, desactivación y sesiones de los usuarios del tenant |
| Gestionar roles | Crear, cambiar y borrar los roles del tenant |
| Consultar la auditoría | Ver los eventos del tenant |
| Gestionar plantillas | Plantillas de taxonomía personalizadas ([Contexto](contexto.md#plantillas-de-taxonomía)) |
| Crear proyectos | Quien crea un proyecto es su propietario |
| Todos los proyectos | Ver y administrar como propietario todos los proyectos del tenant |

- Los roles base **Administrador** (todos los permisos) y **Usuario** («Crear proyectos») no se borran ni cambian.
- Solo puedes dar o quitar permisos que tú tienes. Tampoco puedes asignar a un usuario un rol con permisos que no
  tienes.
- Quitar permisos a un rol cierra las sesiones de sus usuarios.
- Un rol con usuarios no se borra: asígnales otro antes.

## Ubicaciones por tenant

Cada ubicación es de un tenant. La registra el administrador de la instancia en el tenant activo, porque los montajes
son del servidor y un tenant podría apuntar a carpetas de otro. Los usuarios del tenant la ven y la usan en sus
proyectos. Una ubicación solo cambia de tenant si ningún proyecto la usa. Una misma carpeta no puede ser de dos
ubicaciones, y por tanto tampoco de dos tenants ([Ubicaciones](ubicaciones.md)).
