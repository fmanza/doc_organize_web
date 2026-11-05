"""Fase 10 (G38): cuántos documentos lleva convertidos una llamada a doc_organize, a partir de sus ``ProgressEvent``."""

from __future__ import annotations

from app.integrations.doc_organize.scan import ConversionCounter


def test_counts_conversions_and_ocr_and_stops_at_the_limit() -> None:
    counter = ConversionCounter(limit=4)

    assert not counter.feed("discovery", 50)  # el descubrimiento no convierte nada
    assert not counter.feed("conversion", 0)  # documento empezado
    assert not counter.feed("conversion", 1)
    assert not counter.feed("conversion", 1)  # el mismo avance repetido no suma
    assert not counter.feed("conversion", 2)
    assert not counter.feed("ocr", 1)  # el OCR vuelve a empezar en 0 y también cuenta
    assert counter.feed("ocr", 2)
    assert counter.converted == 4


def test_without_limit_it_never_stops() -> None:
    counter = ConversionCounter(limit=0)

    assert not counter.feed("conversion", 10_000)
    assert counter.converted == 10_000


def test_the_last_document_of_the_phase_does_not_stop_the_call() -> None:
    counter = ConversionCounter(limit=2)

    assert not counter.feed("conversion", 1, 2)
    assert not counter.feed("conversion", 2, 2)  # era el último: un tramo nuevo no tendría nada que hacer
    assert not counter.feed("ocr", 0, 3)  # empezar el OCR no es terminar un documento
    assert counter.feed("ocr", 1, 3)  # el OCR que sigue sí tiene pendientes
