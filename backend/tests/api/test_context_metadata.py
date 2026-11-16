"""web 1.5.0 (doc_organize 1.5.0): metadatos y trazabilidad de los documentos del contexto en la API, y sus filtros
(idioma, palabra clave, propuesta de la IA distinta) sobre la proyección en la base de la web."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ContextDocument, ProjectContext
from tests.api.test_context import project  # noqa: F401  (fixture)

DOMAINS = [
    {"slug": "facturas", "name": "Facturas", "description": None, "status": "borrador", "documents": 3},
]


def _doc(seq: int, title: str, **fields: Any) -> ContextDocument:
    return ContextDocument(
        project_id=fields.pop("project_id"),
        seq=seq,
        domain_slug=fields.pop("domain_slug", "facturas"),
        title=title,
        folder="2024",
        path=f"{title}.pdf",
        **fields,
    )


@pytest.fixture
def base(user_client: TestClient, project: dict[str, object], db: Session) -> str:  # noqa: F811
    project_id = int(str(project["id"]))
    db.add(
        ProjectContext(
            project_id=project_id,
            output_folder_name="organizado",
            catalog_kind="domains",
            documents_count=3,
            site_built=False,
            ai_classification=True,
            built_with_version="1.5.0",
            ai_classification_model="clasificador",
            domains=DOMAINS,
        )
    )
    db.flush()
    db.add_all(
        [
            _doc(
                0,
                "enero",
                project_id=project_id,
                author="Ana Pérez",
                description="Factura de suministro eléctrico",
                keywords=["energía", "IVA"],
                language="es",
                rules_domain="facturas",
                rules_confidence=0.82,
            ),
            _doc(
                1,
                "february",
                project_id=project_id,
                description="Resumen de la IA",
                keywords=["invoice"],
                language="en",
                ai_filled=["description"],
                rules_domain="informes",
                rules_confidence=0.31,
                ai_domain="facturas",
                ai_confidence=0.9,
                ai_reasoning="Habla de importes y vencimientos.",
                classified_by="ai",
            ),
            _doc(2, "marzo", project_id=project_id, ai_domain="informes", ai_confidence=0.4, language="es"),
            _doc(3, "suelto", project_id=project_id, domain_slug=None),
        ]
    )
    db.commit()
    return f"/api/v1/projects/{project_id}/context"


def _titles(client: TestClient, url: str, **params: Any) -> list[str]:
    response = client.get(f"{url}/documents", params={"domain": "facturas", **params})
    assert response.status_code == 200, response.text
    return [item["title"] for item in response.json()["items"]]


def test_summary_carries_the_versions_and_models(user_client: TestClient, base: str) -> None:
    summary = user_client.get(base).json()

    assert summary["built_with_version"] == "1.5.0"
    assert summary["ai_classification_model"] == "clasificador"
    assert summary["ai_enrichment_model"] is None


def test_documents_carry_properties_and_how_they_were_classified(user_client: TestClient, base: str) -> None:
    items = user_client.get(f"{base}/documents", params={"domain": "facturas"}).json()["items"]
    enero, february, marzo = items

    assert enero["author"] == "Ana Pérez" and enero["keywords"] == ["energía", "IVA"] and enero["language"] == "es"
    assert (enero["rules_domain"], enero["rules_confidence"], enero["ai_domain"]) == ("facturas", 0.82, None)
    assert february["ai_filled"] == ["description"] and february["ai_reasoning"].startswith("Habla de")
    assert (february["ai_domain"], february["ai_confidence"]) == ("facturas", 0.9)
    assert marzo["keywords"] == [] and marzo["ai_filled"] == [] and marzo["author"] is None


def test_filter_by_language(user_client: TestClient, base: str) -> None:
    assert _titles(user_client, base, language="es") == ["enero", "marzo"]
    assert _titles(user_client, base, language="EN") == ["february"]


@pytest.mark.parametrize(
    ("keyword", "expected"),
    [("iva", ["enero"]), ("energía", ["enero"]), ("ener", ["enero"]), ("voic", ["february"]), ("nada", [])],
)
def test_filter_by_keyword(user_client: TestClient, base: str, keyword: str, expected: list[str]) -> None:
    assert _titles(user_client, base, keyword=keyword) == expected


def test_keyword_filter_does_not_match_the_json_syntax(user_client: TestClient, base: str) -> None:
    assert _titles(user_client, base, keyword='", "') == []
    assert _titles(user_client, base, keyword="%") == []


def test_only_where_the_ai_proposed_another_domain(user_client: TestClient, base: str) -> None:
    assert _titles(user_client, base, only="ai_disagrees") == ["marzo"]


def test_search_looks_at_author_and_description(user_client: TestClient, base: str) -> None:
    assert _titles(user_client, base, q="pérez") == ["enero"]
    assert _titles(user_client, base, q="resumen de la ia") == ["february"]
