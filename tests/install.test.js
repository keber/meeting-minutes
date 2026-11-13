'use strict';

/**
 * Tests del modelo de propiedad framework-owned / user-owned.
 *
 * La regla que estos tests protegen: un upgrade puede pisar cualquier archivo
 * del paquete, pero jamas el vocabulario de dominio del proyecto. Es la leccion
 * de los FRAMEWORK-FIXES del qa-framework, donde cinco arreglos locales
 * desaparecieron en el upgrade siguiente.
 */

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const install = require('../scripts/lib/install');
const initCmd = require('../scripts/init');
const upgradeCmd = require('../scripts/upgrade');

const SKILL_DEST = path.join('.github', 'skills', 'meeting-minutes', 'SKILL.md');
const TEMPLATE_DEST = path.join('.github', 'skills', 'meeting-minutes', 'templates', 'minuta.md');
const COMMAND_DEST = path.join('.claude', 'commands', 'meeting-minutes.md');
const OVERLAY_DEST = path.join('qa', '00-standards', 'minutes', 'domain.json');

/** Proyecto desechable con la config del qa-framework. */
function makeProject(projectName) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'mm-test-'));
  if (projectName) {
    const configDir = path.join(root, 'qa');
    fs.mkdirSync(configDir, { recursive: true });
    fs.writeFileSync(
      path.join(configDir, 'qa-framework.config.json'),
      JSON.stringify({ project: { name: projectName } }),
      'utf8'
    );
  }
  return root;
}

/** init y upgrade resuelven el destino desde INIT_CWD. */
function withProject(root, fn) {
  const previous = process.env.INIT_CWD;
  process.env.INIT_CWD = root;
  const silenced = console.log;
  console.log = () => {};
  try {
    return fn();
  } finally {
    console.log = silenced;
    if (previous === undefined) delete process.env.INIT_CWD;
    else process.env.INIT_CWD = previous;
  }
}

const readOverlay = (root) => JSON.parse(fs.readFileSync(path.join(root, OVERLAY_DEST), 'utf8'));

test('init instala los archivos framework-owned y siembra el overlay', () => {
  const root = makeProject('Proyecto Demo');
  withProject(root, () => initCmd.run([]));

  for (const dest of [SKILL_DEST, TEMPLATE_DEST, COMMAND_DEST, OVERLAY_DEST]) {
    assert.ok(fs.existsSync(path.join(root, dest)), `falta ${dest}`);
  }
  const overlay = readOverlay(root);
  assert.strictEqual(overlay.project, 'Proyecto Demo', 'toma el nombre de qa-framework.config.json');
  assert.deepStrictEqual(overlay.rules, [], 'el overlay se siembra vacio, sin vocabulario de otro proyecto');
  assert.strictEqual(overlay.layer, 'domain');
});

test('el overlay sembrado no arrastra vocabulario del ejemplo', () => {
  const root = makeProject('Otro Proyecto');
  withProject(root, () => initCmd.run([]));

  const seeded = fs.readFileSync(path.join(root, OVERLAY_DEST), 'utf8');
  assert.ok(!seeded.includes('booking'), 'el dominio de ejemplo no puede filtrarse como default');
  assert.ok(!seeded.includes('stacking'));
});

test('init es idempotente', () => {
  const root = makeProject('Demo');
  withProject(root, () => initCmd.run([]));
  const firstRun = fs.readFileSync(path.join(root, SKILL_DEST), 'utf8');

  withProject(root, () => initCmd.run([]));
  assert.strictEqual(fs.readFileSync(path.join(root, SKILL_DEST), 'utf8'), firstRun);
});

test('--dry-run no escribe nada', () => {
  const root = makeProject('Demo');
  withProject(root, () => initCmd.run(['--dry-run']));
  assert.ok(!fs.existsSync(path.join(root, SKILL_DEST)));
  assert.ok(!fs.existsSync(path.join(root, OVERLAY_DEST)));
});

test('upgrade preserva el overlay de dominio y reemplaza la skill editada', () => {
  const root = makeProject('Demo');
  withProject(root, () => initCmd.run([]));

  // El proyecto agrega su vocabulario...
  const overlayPath = path.join(root, OVERLAY_DEST);
  const overlay = JSON.parse(fs.readFileSync(overlayPath, 'utf8'));
  overlay.rules.push({
    id: 'buging_booking',
    pattern: '\\bbuging\\b',
    suggest: 'booking',
    confidence: 'alta',
    reason: 'termino de dominio',
  });
  overlay.people.push({ canonical: 'Ana Perez', display: 'Ana Pérez', aliases: ['Ana'], role: 'QA' });
  fs.writeFileSync(overlayPath, JSON.stringify(overlay, null, 2), 'utf8');

  // ...y alguien parcha la skill a mano.
  const skillPath = path.join(root, SKILL_DEST);
  fs.appendFileSync(skillPath, '\nPARCHE LOCAL\n', 'utf8');

  withProject(root, () => upgradeCmd.run([]));

  const after = readOverlay(root);
  assert.deepStrictEqual(after.rules.map((r) => r.id), ['buging_booking'], 'el overlay sobrevive al upgrade');
  assert.deepStrictEqual(after.people.map((p) => p.display), ['Ana Pérez']);

  assert.ok(
    !fs.readFileSync(skillPath, 'utf8').includes('PARCHE LOCAL'),
    'la skill es framework-owned: el parche local se reemplaza'
  );
});

test('upgrade falla si la skill no esta instalada', () => {
  const root = makeProject('Demo');
  const silenced = console.error;
  console.error = () => {};
  try {
    const code = withProject(root, () => upgradeCmd.run([]));
    assert.strictEqual(code, 1);
  } finally {
    console.error = silenced;
  }
});

test('init --skip-if-exists no toca un proyecto ya instalado', () => {
  const root = makeProject('Demo');
  withProject(root, () => initCmd.run([]));

  const skillPath = path.join(root, SKILL_DEST);
  fs.appendFileSync(skillPath, '\nPARCHE LOCAL\n', 'utf8');

  withProject(root, () => initCmd.run(['--skip-if-exists']));
  assert.ok(
    fs.readFileSync(skillPath, 'utf8').includes('PARCHE LOCAL'),
    'postinstall no debe pisar nada en un proyecto ya instalado; eso es tarea de upgrade'
  );
});

test('isSelfInstall protege al propio paquete y a node_modules', () => {
  assert.strictEqual(install.isSelfInstall(install.PACKAGE_ROOT), true);
  assert.strictEqual(install.isSelfInstall(path.join('/tmp', 'x', 'node_modules', 'y')), true);
  assert.strictEqual(install.isSelfInstall(path.join('/tmp', 'proyecto')), false);
});

test('contentHash ignora BOM y fin de linea', () => {
  const unix = 'linea uno\nlinea dos\n';
  const windows = '﻿linea uno\r\nlinea dos\r\n';
  assert.strictEqual(install.contentHash(unix), install.contentHash(windows));
});
