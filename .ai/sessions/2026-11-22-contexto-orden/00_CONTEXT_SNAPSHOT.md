# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `frontend/src/features/context/ContextPage.tsx` (página, `Summary`, `FreshnessBanner`, `BuildCard`, `Domains`, `HistoryCard`)
- `frontend/src/features/context/ManifestCard.tsx` (editor, `DraftPanel`, `AgentPanel`, `RulesCheck`, `ManifestVersions`)
- `frontend/src/features/context/ProfileCard.tsx`, `Versions.tsx`, `DeliveryCard.tsx`, `AgentPanel.tsx`
- `frontend/src/features/context/ReviewPage.tsx`, `QualityPage.tsx`, `SiteViewerPage.tsx`
- `frontend/src/features/context/useContext.ts` (`Selection`, `initialSelection`, `aiTask`)
- `frontend/src/app/router.tsx` (rutas `projects/:projectId/context[/quality|/review|/site]`, `createBrowserRouter`)
- `frontend/src/i18n/es/features.json` (`context.*`)
- `.github/skills/new-feature/SKILL.md`, `.claude/commands/new-feature.md`
- doc_organize 2.0.1: `context/context_builder.py:479-481` (`compose_profile`), `ai/prompts/__init__.py` (`PromptRegistry`)

## Estado actual observado
- No se han ejecutado tests en esta sesión (solo lectura).
- Sin cambios locales en la web.

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: v2.0.1

## Clasificación metodológica
- Tipo principal: new_feature (reorganización de la interfaz, solo frontend)
- Estado real de alcance: acotado
- Consecuencia: PLAN + AUDIT_PLAN; IMPLEMENT espera aprobación explícita

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica):
- Decisión D1 (visibilidad del perfil) antes de IMPLEMENT; ver `PLAN.md`.
