# 00_REQUEST

- fecha: 2026-11-05
- skill: phase (`phase-implementation`)

```text
/phase

Fase: 10
Alcance: completa
Mejoras opcionales: sí, proponme mejoras
Restricciones: este equipo tiene GPU (RTX 5070 Laptop, 8 GB, driver 616.92); el worker de la cola gpu es la imagen
doc_organize_web-gpu; añade lo que necesites para las pruebas
```

Incluye, por petición del mantenedor (2026-11-05):

- Los cambios de prueba locales sin subir (revisados): menú por proyecto en la barra lateral, aviso de `/mnt` vacía en el
  explorador de carpetas, `docker-compose.override.yml` en `.gitignore`.
- Hallazgos de la prueba manual con documentos reales: botón Duplicados el primero en el proyecto; paginar documentos,
  duplicados y cualquier listado largo; escaneos largos sin morir por OOM (el hotfix 0.10.1 ya da el mensaje correcto).

Antes de la fase: doc_organize 1.0.0rc2 fijada (PR #33) y hotfix 0.10.1 publicado (PR #34, tag `v0.10.1`).
