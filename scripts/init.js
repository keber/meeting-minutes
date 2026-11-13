#!/usr/bin/env node
/**
 * scripts/init.js - Install the meeting-minutes skill into a project.
 *
 * Usage:
 *   meeting-minutes init
 *   meeting-minutes init --dry-run
 *   node scripts/init.js --skip-if-exists     (postinstall)
 *
 * Installs:
 *   .github/skills/meeting-minutes/SKILL.md            framework-owned
 *   .github/skills/meeting-minutes/templates/minuta.md framework-owned
 *   .claude/commands/meeting-minutes.md                framework-owned (thin wrapper)
 *   qa/00-standards/minutes/domain.json                user-owned, seeded once
 *
 * The domain overlay is seeded empty on purpose: one project's vocabulary is not
 * a sensible default for another.
 */

'use strict';

const {
  installClaudeCommand,
  installFrameworkFiles,
  isInstalled,
  isSelfInstall,
  resolveProjectRoot,
  seedUserFiles,
} = require('./lib/install');

const LABEL = {
  created: '[created]',
  updated: '[updated]',
  current: '[current]',
  seeded: '[seeded] ',
  kept: '[kept]   ',
};

function run(argv = process.argv.slice(2)) {
  const dryRun = argv.includes('--dry-run');
  const skipIfExists = argv.includes('--skip-if-exists');
  const projectRoot = resolveProjectRoot();

  if (isSelfInstall(projectRoot)) {
    // postinstall inside the package itself, or inside a dependency tree.
    return 0;
  }

  if (skipIfExists && isInstalled(projectRoot)) {
    return 0;
  }

  console.log(`meeting-minutes init${dryRun ? ' (dry-run)' : ''}`);
  console.log(`Proyecto: ${projectRoot}`);
  console.log('');

  const results = [
    ...installFrameworkFiles(projectRoot, { dryRun }),
    installClaudeCommand(projectRoot, { dryRun }),
    ...seedUserFiles(projectRoot, { dryRun }),
  ];

  for (const r of results) {
    console.log(`  ${LABEL[r.action] || r.action} ${r.dest}`);
  }

  const seeded = results.find((r) => r.key === 'domain' && r.action === 'seeded');
  console.log('');
  if (seeded) {
    console.log('Siguiente paso: completar el overlay de dominio del proyecto en');
    console.log(`  ${seeded.dest}`);
    console.log('con los terminos que el motor de transcripcion destruye (siglas, nombres');
    console.log('propios, vocabulario del negocio). Sin eso, el cruce con Azure DevOps');
    console.log('pierde precision: esos terminos son las keywords del matching.');
  } else {
    console.log('El overlay de dominio ya existia y no fue tocado.');
  }

  return 0;
}

if (require.main === module) {
  process.exitCode = run();
}

module.exports = { run };
