"""Paso a doc_organize 1.6.0 (W2): sin clasificar con su motivo y sus propiedades (G42), y lo que borra el contexto.

Contra los modelos reales de la librería, sin Docling.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from doc_organize import ProjectLayout, UnclassifiedDocument

from app.integrations.doc_organize import context
from app.jobs.operations.context import _row


def _detail(path: str, reason: str, **fields: object) -> UnclassifiedDocument:
    return UnclassifiedDocument(
        source_path=path,
        title=fields.pop("title", Path(path).stem),
        document_type="pdf",
        reason=reason,  # type: ignore[arg-type]
        **fields,  # type: ignore[arg-type]
    )


def _context(paths: list[str], details: list[UnclassifiedDocument]) -> SimpleNamespace:
    return SimpleNamespace(unclassified_documents=paths, unclassified_details=details)


def test_unclassified_carry_reason_rules_and_properties() -> None:
    details = [
        _detail(
            "/origen/a.pdf",
            "below_threshold",
            title="Política de copias",
            rules_domain="seguridad-informatica",
            rules_confidence=0.5,
            author="Ana",
            description="Copias de seguridad",
            keywords=["copias"],
            language="es",
        ),
        _detail("/origen/b.pdf", "incomplete_artifacts"),
    ]

    a, b = context._unclassified(_context(["/origen/a.pdf", "/origen/b.pdf"], details))

    assert (a.title, a.unclassified_reason, a.rules_domain, a.rules_confidence) == (
        "Política de copias",
        "below_threshold",
        "seguridad-informatica",
        0.5,
    )
    assert (a.author, a.description, a.keywords, a.language) == ("Ana", "Copias de seguridad", ["copias"], "es")
    assert a.domain_slug is None and a.organized_path is None
    assert (b.unclassified_reason, b.rules_domain, b.rules_confidence) == ("incomplete_artifacts", None, None)


def test_a_context_from_1_5_falls_back_to_the_paths() -> None:
    (doc,) = context._unclassified(_context(["/origen/Informe.DOCX"], []))

    assert (doc.title, doc.document_type, doc.unclassified_reason) == ("Informe.DOCX", "docx", None)


def test_details_that_do_not_match_the_paths_are_not_used() -> None:
    # La librería ya los alinea al cargar; si aun así no cuadran, mejor sin metadatos que con los de otro documento.
    details = [_detail("/origen/otro.pdf", "below_threshold")]

    (doc,) = context._unclassified(_context(["/origen/a.pdf"], details))

    assert (doc.source_path, doc.unclassified_reason) == ("/origen/a.pdf", None)


def test_the_job_keeps_the_reason_only_for_unclassified() -> None:
    namer = SimpleNamespace(split=lambda path: ("2024", Path(path).name))
    unclassified = context.ContextDoc(
        domain_slug=None,
        title="a",
        document_type="pdf",
        material_type=None,
        material_type_name=None,
        source_path="/origen/2024/a.pdf",
        organized_path=None,
        unclassified_reason="below_threshold",
    )
    classified = context.ContextDoc(**{**unclassified.__dict__, "domain_slug": "facturas"})

    assert _row(1, 0, unclassified, namer)["unclassified_reason"] == "below_threshold"  # type: ignore[arg-type]
    assert _row(1, 1, classified, namer)["unclassified_reason"] is None  # type: ignore[arg-type]


def test_the_delete_preview_lists_unclassified_json_but_not_the_history(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)

    paths = context.context_paths(tmp_path, "organizado")

    assert Path(layout.unclassified_file) in paths
    assert not any("historial" in str(path) for path in paths)
