# Política de seguridad

## Versiones con soporte

doc_organize_web está en planificación (sin releases). Desde la primera versión publicada, solo la última MINOR
recibe correcciones de seguridad.

| Versión | Soporte |
|---|---|
| `main` / `develop` | ✅ |
| Releases | — (aún no hay) |

## Cómo reportar una vulnerabilidad

**No abras un issue público.** Usa el reporte privado de GitHub:

1. Pestaña **Security** del repositorio → **Report a vulnerability**
   (<https://github.com/fmanza/doc_organize_web/security/advisories/new>).
2. Incluye: componente afectado (backend, frontend, imagen Docker), versión o commit, pasos para reproducir,
   impacto y, si la tienes, una propuesta de corrección.

Compromiso orientativo: acuse de recibo en 5 días hábiles y evaluación inicial en 10. Si se confirma, se prepara la
corrección en privado, se publica un *security advisory* y se reconoce al autor del reporte salvo que prefiera el
anonimato.

## Alcance

Dentro: la API (`backend/`), la SPA (`frontend/`), la imagen y el `docker-compose.yml` de este repositorio, y la
integración con [doc_organize](https://github.com/fmanza/doc_organize).

Fuera: vulnerabilidades de dependencias de terceros ya publicadas (Dependabot las gestiona), configuraciones de
despliegue que contradigan la guía (contenedor como root, sin proxy TLS, secretos en el repositorio) y ataques que
requieran acceso previo de administrador al servidor.

## Medidas del repositorio

*Secret scanning* con *push protection*, alertas y actualizaciones de seguridad de Dependabot, CodeQL y ramas
`main`/`develop` protegidas (solo por PR). Detalle en [docs/plan/DECISIONES_Y_RIESGOS.md](docs/plan/DECISIONES_Y_RIESGOS.md).
