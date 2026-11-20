"""Prueba de preproducción de la 2.0 (W9) contra una instancia **aislada** ya levantada (``scripts/preprod/up.sh``).

Recorre por la API lo que hará una persona: diagnóstico (con los modelos de IA si se pide), ubicaciones de origen (solo
lectura) y destino, un proyecto nuevo, escaneo, construcción del contexto y las tres entregas (Excel del contexto, sitio
sin conexión y paquete para IA), descargando cada fichero y comprobando que su SHA-256 es el que dice la aplicación.

No escribe en el origen (la ubicación se registra de solo lectura y el montaje es ``:ro``). Solo imprime recuentos,
estados y huellas: ni nombres de documentos ni rutas ni claves. La contraseña del admin se lee de
``DOW_PREPROD_PASSWORD`` o, si no está, de la entrada estándar; la clave de IA (opcional) de la variable cuyo nombre se da
en ``--ai-key-env`` y nunca se imprime.

Uso (con la instancia de ``scripts/preprod/up.sh``)::

    printf '%s\\n' "$PASSWORD" | python scripts/preprod_smoke.py --url http://127.0.0.1:18090 --user preprod-admin \\
        --source origen --folder . --destination salidas --template calidad

Sale con 0 si todo terminó bien.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.cookies import SimpleCookie
from typing import Any

POLL_SECONDS = 3.0


class Client:
    """Cliente mínimo de la API (cookies de sesión y CSRF a mano: funcionan también en http)."""

    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")
        self.cookies: dict[str, str] = {}
        self.csrf = ""

    def request(self, method: str, path: str, body: Any = None, *, raw: bool = False) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if method != "GET":
            headers["X-CSRF-Token"] = self.csrf
        if self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        request = urllib.request.Request(self.url + path, data=data, headers=headers, method=method)  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=600) as response:  # noqa: S310 - URL de la instancia aislada
                for header in response.headers.get_all("Set-Cookie") or []:
                    for name, morsel in SimpleCookie(header).items():
                        self.cookies[name] = morsel.value
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise SystemExit(f"{method} {path}: HTTP {exc.code} {detail}") from None
        if raw:
            return payload
        return json.loads(payload) if payload else None

    def refresh_csrf(self) -> None:
        self.csrf = self.request("GET", "/api/v1/auth/csrf")["csrf_token"]


def step(message: str) -> None:
    print(f"\n== {message}", flush=True)


def wait_run(client: Client, run_id: str, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        run = client.request("GET", f"/api/v1/runs/{run_id}")
        if run["status"] in {"succeeded", "failed", "cancelled"}:
            print(f"   run {run['operation']}: {run['status']}", flush=True)
            if run["status"] != "succeeded":
                raise SystemExit(f"   falló: {run.get('error_code')}: {run.get('error_message')}")
            return dict(run)
        if time.monotonic() > deadline:
            raise SystemExit(f"   sin terminar tras {timeout:.0f} s (sigue en la instancia: {run_id})")
        time.sleep(POLL_SECONDS)


def run(client: Client, project_id: int, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    created = client.request("POST", f"/api/v1/projects/{project_id}/runs", body)
    return wait_run(client, created["id"], timeout)


def location(client: Client, name: str, path: str, usage: str, access: str) -> int:
    for item in client.request("GET", "/api/v1/locations?limit=200")["items"]:
        if item["name"] == name:
            return int(item["id"])
    created = client.request(
        "POST", "/api/v1/locations", {"name": name, "path": path, "usage": usage, "access": access}
    )
    return int(created["id"])


def check_download(client: Client, run_data: dict[str, Any]) -> None:
    for artifact in run_data["artifacts"]:
        if artifact["kind"] != "output":  # el log del run no es la entrega
            continue
        data = client.request("GET", f"/api/v1/runs/{run_data['id']}/artifacts/{artifact['id']}", raw=True)
        digest = hashlib.sha256(data).hexdigest()
        expected = (run_data.get("result") or {}).get("sha256")
        state = "sin huella en el resultado" if not expected else ("coincide" if expected == digest else "NO COINCIDE")
        print(f"   {artifact['kind']}: {len(data)} bytes, SHA-256 {digest} ({state})")
        if expected and expected != digest:
            raise SystemExit("   el SHA-256 descargado no es el de la aplicación")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="URL de la instancia aislada (no la de producción)")
    parser.add_argument("--user", required=True, help="admin de la instancia aislada")
    parser.add_argument("--source", default="origen", help="carpeta bajo /mnt con el origen (montado :ro)")
    parser.add_argument("--folder", action="append", default=[], help="subcarpeta del origen a escanear (repetible)")
    parser.add_argument("--destination", default="salidas", help="carpeta bajo /mnt para las salidas")
    parser.add_argument("--template", help="plantilla de taxonomía (sin ella, dominios descubiertos)")
    parser.add_argument("--ai-url", help="URL del LiteLLM para la IA (opcional)")
    parser.add_argument("--ai-key-env", default="LiteLLM", help="variable de entorno con la clave virtual")
    parser.add_argument("--ai", action="store_true", help="construir con IA para lo que las reglas no clasifican")
    parser.add_argument("--diagnostics-ai", action="store_true", help="probar también los modelos en el diagnóstico")
    parser.add_argument("--scan-timeout", type=float, default=4 * 3600)
    args = parser.parse_args(argv)
    password = os.environ.get("DOW_PREPROD_PASSWORD") or sys.stdin.readline().strip()
    client = Client(args.url)

    step("Inicio de sesión")
    client.refresh_csrf()
    client.request("POST", "/api/v1/auth/login", {"username": args.user, "password": password})
    client.refresh_csrf()
    health = client.request("GET", "/api/health")
    print(f"   web {health['version']}, doc_organize {health['doc_organize_version']}, worker {health['worker']}")

    if args.ai_url:
        step("Modelos de IA (clave de la variable de entorno; no se imprime)")
        key = os.environ.get(args.ai_key_env)
        if not key:
            raise SystemExit(f"   falta la variable de entorno {args.ai_key_env}")
        client.request(
            "PUT", "/api/v1/admin/ai-settings/litellm", {"fields": {"base_url": args.ai_url, "virtual_key": key}}
        )
        print("   configurada")

    step("Diagnóstico")
    report = client.request("POST", "/api/v1/admin/diagnostics", {"check_ai": args.diagnostics_ai})
    for check in report["checks"]:
        print(f"   {check['status']:8} {check['name']}")
    errors = [check["name"] for check in report["checks"] if check["status"] == "error"]
    print(f"   errores: {len(errors)}")

    step("Ubicaciones y proyecto")
    source = location(client, "Preproducción origen", args.source, "source", "ro")
    destination = location(client, "Preproducción salidas", args.destination, "destination", "rw")
    name = f"Preproducción {time.strftime('%Y%m%d-%H%M%S')}"
    project = client.request(
        "POST",
        "/api/v1/projects",
        {
            "name": name,
            "source_location_id": source,
            "source_subpaths": args.folder or [""],
            "destination_location_id": destination,
            "destination_parent": "",
            "new_folder": name,
        },
    )
    project_id = int(project["id"])
    print(f"   proyecto {project_id}")

    step("Escaneo")
    scan = run(client, project_id, {"operation": "scan"}, args.scan_timeout)
    result = scan.get("result") or {}
    print(
        f"   escaneados {result.get('scanned')}, convertidos {result.get('converted')}, errores {result.get('errors')}"
    )

    step("Contexto")
    build: dict[str, Any] = {"operation": "context_build", "ai_classification": args.ai}
    if args.template:
        build |= {"catalog": "template", "template_name": args.template}
    built = run(client, project_id, build, args.scan_timeout)
    result = built.get("result") or {}
    print(f"   dominios {result.get('domains')}, sin clasificar {result.get('unclassified')}")
    print(f"   sitio construido {result.get('site_built')}, IA {json.dumps(result.get('ai'))[:200]}")

    step("Entregas")
    for body in (
        {"operation": "export_xlsx", "kind": "context_documents"},
        {"operation": "export_site", "llms_txt": True},
        {"operation": "export_ai_bundle"},
    ):
        delivered = run(client, project_id, body, 3600)
        check_download(client, delivered)

    step("Resultado")
    if errors:
        print(f"   El diagnóstico tiene errores: {', '.join(errors)}")
        return 1
    print("   Todo correcto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
