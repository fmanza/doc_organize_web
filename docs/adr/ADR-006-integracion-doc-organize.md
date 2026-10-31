# ADR-006 — Integración con doc_organize: capa anticorrupción y versión fijada

- **Estado**: Aceptado (implementado en la Fase 0, 0.1.0)
- **Fecha**: 2026-10-31

## Contexto

doc_organize evoluciona en paralelo (tareas `L-*`): su API pública cambiará en 0.10.0 y 0.11.0 y su web integrada se
retirará en 1.0.0. La web debe poder actualizarla sin reescribir dominio ni API, y el build y el CI deben ser
reproducibles sin credenciales. Hasta el 2026-10-31 no había wheel publicado de la 0.9.x (G9) y el tag `v0.9.2` no
coincidía con la versión del paquete (G14).

## Decisión

1. **Capa anticorrupción**: solo `backend/app/integrations/doc_organize/` importa `doc_organize` (y `docling`).
   Expone funciones y tipos propios; lo verifica `backend/tests/unit/test_architecture.py`.
2. **Wheel de la release**: doc_organize **0.9.3** se publicó con wheel y sdist en GitHub Releases para la Fase 0.
   `[tool.uv.sources]` apunta a
   `https://github.com/fmanza/doc_organize/releases/download/v0.9.3/doc_organize-0.9.3-py3-none-any.whl` y
   `uv.lock` fija su SHA-256; `uv sync --frozen` rechaza un wheel con otro hash.
3. **Extras**: `ai` y `context`. Los extras `export` y `site` llegarán con doc_organize 0.11.0 (L-7, L-8);
   RapidOCR ya viene en sus dependencias base (`docling[rapidocr]`).
4. **torch CPU**: docling exige `torch` y `torchvision`; en Linux los de PyPI incluyen CUDA (varios GB). Se resuelven
   desde el índice CPU de PyTorch (`[[tool.uv.index]] pytorch-cpu`, `explicit = true`). La variante GPU (Fase 4)
   tendrá su propia resolución.
5. **Versión de la librería** leída de los metadatos (`importlib.metadata`), no de `doc_organize.__version__` (G1) y
   sin importar Docling.
6. **Actualizar doc_organize**: comprobar que la release tiene el wheel, cambiar la versión en `dependencies` y la URL
   en `[tool.uv.sources]`, `uv lock`, suite y tests de contrato de la capa, nota en el CHANGELOG y en la columna
   «Requiere» del ROADMAP. Dependabot ignora `doc_organize`, `torch` y `torchvision`.
7. **Huecos**: cada carencia de la API va a `docs/plan/DOC_ORGANIZE_GAPS.md` con su rodeo temporal en la capa
   (comentario con su `G<n>`); nunca se parchea la librería desde la web.

## Alternativas descartadas

- Vendorizar un wheel construido desde el tag `v0.9.2`: el paquete se habría llamado 0.9.0 (G14) y el repositorio
  arrastraría un binario.
- `git+https://…@tag`: construiría la librería en cada build.
- Ruta local `../doc_organize`: el build dependería del árbol de trabajo, no de una versión.
