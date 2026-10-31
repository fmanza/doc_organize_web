# Contribuir

Gracias por el interés. Antes de abrir un PR:

1. **Repositorio público**: nunca subas documentos, rutas internas, nombres de servidores, capturas con datos ni
   credenciales reales. Los tests usan documentos sintéticos generados por el propio test.
2. **Vulnerabilidades**: en privado, según [SECURITY.md](SECURITY.md); nunca en un issue.
3. **Ramas**: trabaja en una rama desde `develop` (`feat/…`, `fix/…`, `docs/…`) y abre el PR contra `develop`.
   `main` solo recibe releases.
4. **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) con scope opcional (`backend`,
   `frontend`, `docker`, `docs`, `ia`).
5. **Validación**: los comandos de [docs/guides/desarrollo.md](docs/guides/desarrollo.md) en verde (backend,
   frontend, documentación). Si cambias la API, exporta `openapi/openapi.json` y regenera el cliente en el mismo PR.
6. **doc_organize**: no se modifica desde aquí. Si te falta algo de su API, regístralo en
   [docs/plan/DOC_ORGANIZE_GAPS.md](docs/plan/DOC_ORGANIZE_GAPS.md).

Las reglas completas (arquitectura, seguridad, tests) están en
[.github/SHARED_INSTRUCTIONS.md](.github/SHARED_INSTRUCTIONS.md) y [.github/instructions/](.github/instructions/).
