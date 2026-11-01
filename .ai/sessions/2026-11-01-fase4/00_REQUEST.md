# REQUEST

## Session metadata
- id: 2026-11-01-fase4
- fecha: 2026-11-01
- rama: feature/fase-4 (desde develop b5e9d07)
- skill: phase
- fase solicitada: PLAN + AUDIT_PLAN de la Fase 4 (Escaneo y conversión → 0.5.0)

## Solicitud original saneada
/phase — Fase: 4. Inputs completados por el mantenedor (2026-11-01):
- Alcance: completa (WB-4.1, WB-4.2, WB-4.3, WF-4.1).
- Mejoras opcionales: sí, variante GPU (resolución de dependencias CUDA, imagen `runtime-gpu`, worker de la cola `gpu`).
- Restricciones: doc_organize 0.10.0 (wheel de la release); hay GPU para probar; la API no importa doc_organize (G15).
- Requisito de entrada Pillow ≥ 13: **excepción de seguridad ya** (no esperar al 2026-11-05).

## Restricciones explícitas
- Excepciones `exclude-newer-package` solo para los paquetes docling que levantan el límite `pillow<13`.
- Detenerse tras AUDIT_PLAN.
