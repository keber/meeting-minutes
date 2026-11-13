#!/usr/bin/env node
/**
 * scripts/cli.js - Entry point for the `meeting-minutes` binary.
 *
 * Commands:
 *   meeting-minutes init [--dry-run]      install the skill into this project
 *   meeting-minutes upgrade [--dry-run]   refresh framework-owned files
 *
 * Transcript processing itself runs through Python:
 *   python -m tgd <transcript> --domain <overlay> --fix
 */

'use strict';

const COMMANDS = {
  init: () => require('./init').run(process.argv.slice(3)),
  upgrade: () => require('./upgrade').run(process.argv.slice(3)),
};

function usage() {
  console.log('Uso: meeting-minutes <init|upgrade> [--dry-run]');
  console.log('');
  console.log('  init      Instala la skill en el proyecto actual');
  console.log('  upgrade   Actualiza los archivos framework-owned');
  console.log('');
  console.log('Para procesar una transcripcion:');
  console.log('  python -m tgd <transcripcion> --domain qa/00-standards/minutes/domain.json --fix');
}

const command = process.argv[2];
if (!command || command === '--help' || command === '-h') {
  usage();
  process.exitCode = command ? 0 : 1;
} else if (COMMANDS[command]) {
  process.exitCode = COMMANDS[command]();
} else {
  console.error(`Comando desconocido: ${command}`);
  usage();
  process.exitCode = 1;
}
