// npm-runnable shim for gen_i18n_fallback.py: tries python3 / python / py so
// the same `npm run build` works on Linux CI and a Windows laptop alike.
// Windows quirk: `python3` may be a Microsoft Store alias stub that runs and
// fails instead of ENOENT-ing — so every candidate gets a try, first success
// wins, and only then do we give up with the last real exit code.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('./gen_i18n_fallback.py', import.meta.url));

let last = null;
for (const cmd of ['python3', 'python', 'py']) {
  const r = spawnSync(cmd, [script], { stdio: 'inherit' });
  if (r.status === 0) process.exit(0);
  if (!r.error) last = r.status;      // it ran and failed — remember, keep trying
}
console.error('gen-i18n-fallback: no working python interpreter (python3/python/py)');
process.exit(last ?? 1);
