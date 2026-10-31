# Montar carpetas de red

La aplicación **no** monta carpetas ni guarda credenciales de red ([ADR-007](../adr/ADR-007-ubicaciones.md)). El
administrador del servidor Linux monta los recursos SMB/NFS en el host y los pasa al contenedor bajo `/mnt`; después,
un administrador de la aplicación los registra como **ubicaciones** ([Ubicaciones](ubicaciones.md)).

Los nombres de servidor de esta guía son ficticios (`nas.example.internal`): sustitúyelos por los tuyos.

## 1. Montar en el host

Paquetes: `cifs-utils` (SMB) o `nfs-common` (NFS).

### SMB / CIFS

Credenciales en un fichero solo legible por root:

```bash
sudo install -m 600 /dev/null /etc/dow-nas.credentials
sudoedit /etc/dow-nas.credentials
#   username=<usuario>
#   password=<contraseña>
#   domain=<dominio>
sudo mkdir -p /srv/dow/expedientes
```

Entrada en `/etc/fstab` (solo lectura, propietario el uid 10001 del contenedor):

```text
//nas.example.internal/expedientes  /srv/dow/expedientes  cifs  ro,credentials=/etc/dow-nas.credentials,uid=10001,gid=10001,vers=3.1.1,_netdev,nofail  0  0
```

### NFS

```text
nas.example.internal:/export/expedientes  /srv/dow/expedientes  nfs  ro,hard,timeo=600,retrans=2,_netdev,nofail  0  0
```

### Aplicar

```bash
sudo mount -a
ls /srv/dow/expedientes
```

Usa `rw` solo en las carpetas de **destino** (salidas) o si quieres permitir resolver duplicados moviendo en el origen
(Fase 6). `nofail` evita que el servidor no arranque si el recurso no está disponible.

## 2. Pasarlas al contenedor

Crea `docker-compose.override.yml` junto a `docker-compose.yml` (Compose lo lee solo):

```yaml
services:
  web:
    volumes:
      - /srv/dow/expedientes:/mnt/expedientes:ro
      - /srv/dow/salidas:/mnt/salidas
  worker:
    volumes:
      - /srv/dow/expedientes:/mnt/expedientes:ro
      - /srv/dow/salidas:/mnt/salidas
```

El `web` y el `worker` deben ver **las mismas** rutas bajo `/mnt`. Aplica con `docker compose up -d`.

## 3. Registrar la ubicación

En la aplicación, **Ubicaciones → Nueva ubicación**, elige la carpeta en `/mnt` y pulsa **Comprobar**: el estado debe
ser «Disponible». Si sale «Degradada» o «No disponible», el motivo aparece al pasar por encima del estado.

## Nunca

- Nunca montes la carpeta del volumen `data` (bases SQLite) en una unidad de red: SQLite no es fiable sobre SMB/NFS
  ([ADR-005](../adr/ADR-005-workspace-estado-y-salidas.md)).
- Nunca pongas credenciales de red en `docker-compose.yml`, `.env` ni en la aplicación.

## Desarrollo con Docker Desktop

En Windows/macOS las unidades de red mapeadas no son visibles para el contenedor (R1): usa carpetas locales
(`docker-compose.dev.yml` monta `dev-data/locations/origen` y `destino`) y prueba las de red en el servidor Linux.
