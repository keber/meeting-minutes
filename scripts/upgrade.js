#!/usr/bin/env node
/**
 * scripts/upgrade.js - Refresh framework-owned files in an existing project.
 *
 * Usage:
 *   meeting-minutes upgrade
 *   meeting-minutes upgrade --dry-run
 *
 * ALWAYS updates (framework-owned):
 *   .github/skills/meeting-minutes/SKILL.md
 *   .github/skills/meeting-minutes/templates/minuta.md
 *   .claude/commands/meeting-minutes.md
 *
 * NEVER touches (user-owned):
 *   qa/00-standards/minutes/domain.json   <- the project's domain vocabulary
 *   any minute already written
 *   any transcript, raw or corrected
 *
 * A local edit to a framework-owned file is reported before being replaced, so a
 * fix worth keeping can be promoted upstream instead of silently disappearing on
 * the next upgrade.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const {
  installClaudeCommand,
  installFrameworkFiles,
  isInstalled,
  isSelfInstall,
  resolveProjectRoot,
  USER_SEEDS,
} = require('./lib/install');

function describeDomainOverlay(projectRoot) {
  const seed = USER_SEEDS.find((s) => s.key === 'domain');
  const destPath = path.join(projectRoot, seed.dest);

  if (!fs.existsSync(destPath)) {
    return `  [ausente] ${seed.dest} - ejecutar 'meeting-minutes init' para sembrarlo`;
  }
  try {
    const overlay = JSON.parse(fs.readFileSync(destPath, 'utf8'));
    const rules = Array.isArray(overlay.rules) ? overlay.rules.length : 0;
    const people = Array.isArray(overlay.people) ? overlay.people.length : 0;
    return `  [intacto]  ${seed.dest} (${rules} reglas, ${people} personas)`;
  } catch (e) {
    return `  [ilegible] ${seed.dest} - no es JSON valido (${e.message})`;
  }
}

function run(argv = process.argv.slice(2)) {
  const dryRun = argv.includes('--dry-run');
  const projectRoot = resolveProjectRoot();

  if (isSelfInstall(projectRoot)) {
    console.error('No hay proyecto destino: este comando corre dentro de un proyecto, no del paquete.');
    return 1;
  }

  console.log(`meeting-minutes upgrade${dryRun ? ' (dry-run)' : ''}`);
  console.log(`Proyecto: ${projectRoot}`);
  console.log('');

  if (!isInstalled(projectRoot)) {
    console.error("La skill no esta instalada en este proyecto. Ejecutar 'meeting-minutes init' primero.");
    return 1;
  }

  const results = [
    ...installFrameworkFiles(projectRoot, { dryRun }),
    installClaudeCommand(projectRoot, { dryRun }),
  ];

  console.log('Framework-owned:');
  const overwritten = [];
  for (const r of results) {
    if (r.action === 'updated') overwritten.push(r.dest);
    console.log(`  [${r.action}] ${r.dest}`);
  }

  console.log('');
  console.log('User-owned (nunca se sobreescribe):');
  console.log(describeDomainOverlay(projectRoot));

  if (overwritten.length) {
    console.log('');
    console.log('Aviso: los siguientes archivos tenian cambios locales y fueron reemplazados:');
    for (const dest of overwritten) console.log(`  - ${dest}`);
    console.log('Si alguno de esos cambios vale la pena, promoverlo al paquete; de lo');
    console.log('contrario se vuelve a perder en el proximo upgrade.');
  }

  return 0;
}

if (require.main === module) {
  process.exitCode = run();
}

module.exports = { run };
