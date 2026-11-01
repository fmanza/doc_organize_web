# Proyectos

Un **proyecto** junta lo que necesita doc_organize para trabajar con un conjunto de documentos:

- **Origen**: una [ubicación](ubicaciones.md) de origen y una o varias de sus carpetas. Solo se lee.
- **Destino**: una carpeta **propia del proyecto** dentro de una ubicación de destino con lectura y escritura. Ahí se
  escriben las salidas (Markdown, JSON, imágenes, duplicados, sitio de contexto).
- **Miembros**: quién puede verlo y qué puede hacer.

La caché y el historial de doc_organize no van al destino (que puede ser una carpeta de red): la aplicación los guarda
en su propio disco.

## Crear un proyecto

**Proyectos → Nuevo proyecto** (cualquier usuario; quien lo crea queda como **propietario**):

1. Nombre y, si quieres, una descripción.
2. **Ubicación de origen** y sus carpetas: navega y pulsa «Elegir esta carpeta» en cada una (hasta 20). Una carpeta no
   puede estar dentro de otra de la lista: cada documento se convierte a una ruta que depende de su carpeta
   ([Escaneo](escaneo.md)).
3. **Ubicación de destino** y la carpeta de salidas, de una de estas formas:
    - **Crear carpeta nueva**: elige dónde y escribe el nombre. No puede existir ya.
    - **Usar una carpeta vacía**: tiene que estar vacía.

La carpeta de salidas pasa a **pertenecer al proyecto**: vaciar o borrar el proyecto puede borrar todo su contenido,
por eso no se acepta una carpeta con ficheros. Tampoco puede estar dentro del origen (ni contenerlo) ni coincidir con
la de otro proyecto.

## Roles

| Rol | Puede |
|---|---|
| Lector | Ver el proyecto, sus miembros, sus ejecuciones y los errores de escaneo, y descargar sus ficheros |
| Editor | Lo anterior, escanear y cancelar sus ejecuciones |
| Propietario | Todo: editar el proyecto y sus carpetas de origen, gestionar miembros, cancelar cualquier ejecución, forzar la reconversión, mover, vaciar y borrar |

Los administradores ven todos los proyectos y actúan como propietarios. Un proyecto del que no eres miembro no aparece
y su enlace responde «Proyecto no encontrado».

**Miembros**: el propietario busca a un usuario activo (al menos dos letras), elige el rol y pulsa «Añadir». Siempre
queda al menos un propietario.

## Editar

«Editar» cambia el nombre y la descripción. **Cambiar el nombre no renombra la carpeta de salidas.** Las carpetas de
origen se añaden y se quitan desde la pantalla de **Escanear**, sin ejecuciones en marcha.

## Mover, vaciar y borrar (zona de peligro)

Solo propietarios, y solo si no hay otra ejecución en marcha en el proyecto. Las tres siguen los mismos pasos:

1. **Ver vista previa**: se lanza una ejecución que **no cambia nada** y cuenta lo que se tocará (ficheros y tamaño).
2. Si estás de acuerdo, **escribe el nombre del proyecto** y confirma. La vista previa vale 15 minutos; si cambias las
   opciones o el proyecto cambia entretanto, hay que repetirla.

| Operación | Qué hace |
|---|---|
| **Mover salidas** | Lleva la carpeta de salidas a una carpeta nueva de otra ubicación de destino (o de la misma). En el mismo disco es instantáneo; entre ubicaciones distintas se copia y después se borra la carpeta anterior. Si la copia falla o la cancelas, se deshace y el proyecto no cambia |
| **Vaciar histórico** | Borra las salidas y la caché; el proyecto, sus miembros y su configuración se conservan, listo para volver a procesar desde cero |
| **Borrar proyecto** | El proyecto desaparece de la lista y su caché se borra. Con «Borrar también la carpeta de salidas» se borra esa carpeta; si no, se queda en el destino. El historial de ejecuciones se conserva |

Todas quedan en la auditoría con quién, cuándo y cuántos ficheros.

## Probar el motor

«Probar el motor» (solo administradores) lanza una ejecución de prueba (cinco pasos de un segundo) que no toca los
documentos: sirve para comprobar que el worker está en marcha y ver el progreso en vivo. Para convertir documentos,
**Escanear** ([Escaneo](escaneo.md)).
