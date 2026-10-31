# TRACEABILITY

## Session metadata
- id: YYYY-MM-DD
- fecha: YYYY-MM-DD
- rama: <!-- rama activa -->
- skill: <!-- phase | new_feature | hotfix | refactor | audit_code | security_review | tech_debt | documentation | config_review | version_closure -->
- fase: <!-- fases ejecutadas, p.ej. PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE -->

## Prompt issued
<!-- Solicitud original tal como llegó al agente, sin editar. -->

## Context supplied
<!-- Lista de fuentes de contexto proporcionadas al agente antes de la primera respuesta. -->
-

## AI output summary
<!-- Resumen cronológico de las acciones y decisiones del agente, una línea por acción relevante.
     No inventar; solo documentar lo que realmente se ejecutó y decidió.
     Incluir: archivos creados/modificados, tests corridos, validaciones realizadas, veredictos emitidos. -->
-

## Artefactos generados
<!--
| Artefacto        | Ruta                       | Estado     |
|------------------|----------------------------|------------|
| PLAN             | .ai/sessions/YYYY-MM-DD/…  | emitido    |
| IMPLEMENT        | backend/… · frontend/…                      | completado |
-->

## Directrices para Futuras IAs
<!--
Registra conocimiento descubierto DURANTE o DESPUÉS de la sesión que una IA futura necesita
para no repetir análisis ni tomar decisiones erróneas en el mismo dominio.
Usar formato: "**[área]**: <hecho verificable>".
-->
-

## Veredicto final
<!-- GO | GO_CONDICIONAL | NO_GO | CLOSED -->
Veredicto:
Pendientes al cierre:
-
