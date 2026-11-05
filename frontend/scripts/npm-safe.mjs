// Regla de versiones con ≥ 2 semanas (ADR-001 §6, reactivada en la Fase 10): `npm install` con
// `--before=<hoy - 14 días>`, para añadir o subir dependencias solo a versiones publicadas hace al menos 14 días.
//   npm run safe -- install --save-exact paquete@1.2.3
// `npm ci` no lo necesita: instala lo fijado en package-lock.json.
import { spawnSync } from 'node:child_process';

const DAYS = 14;
const before = new Date(Date.now() - DAYS * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
const args = [...process.argv.slice(2), `--before=${before}`];
console.log(`npm ${args.join(' ')}`);
const result = spawnSync('npm', args, { stdio: 'inherit', shell: process.platform === 'win32' });
process.exit(result.status ?? 1);
