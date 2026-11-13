'use strict';

/**
 * scripts/lib/install.js - Shared install primitives for init and upgrade.
 *
 * Ownership model, mirrored from @keber/qa-framework:
 *   framework-owned -> always overwritten, so every project runs the current logic
 *   user-owned      -> seeded once, then never touched again
 *
 * A file counts as "pristine" when its normalised sha256 matches what this package
 * currently ships. Anything else is a local edit and is preserved, with a warning.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PACKAGE_ROOT = path.resolve(__dirname, '..', '..');

const SKILL_NAME = 'meeting-minutes';

// Framework-owned: source in this package -> destination in the target project.
const FRAMEWORK_FILES = [
  {
    key: 'skill',
    src: path.join('skills', SKILL_NAME, 'SKILL.md'),
    dest: path.join('.github', 'skills', SKILL_NAME, 'SKILL.md'),
  },
  {
    key: 'template',
    src: path.join('templates', 'minuta.md'),
    dest: path.join('.github', 'skills', SKILL_NAME, 'templates', 'minuta.md'),
  },
];

// User-owned: seeded once if absent, never overwritten.
const USER_SEEDS = [
  {
    key: 'domain',
    dest: path.join('qa', '00-standards', 'minutes', 'domain.json'),
    build: buildDomainSeed,
  },
];

/** Normalised hash: BOM and line endings must not make a file look edited. */
function contentHash(content) {
  const normalised = content.replace(/^﻿/, '').replace(/\r\n/g, '\n');
  return crypto.createHash('sha256').update(normalised, 'utf8').digest('hex');
}

function isPristine(filePath, shippedContent) {
  let current;
  try {
    current = fs.readFileSync(filePath, 'utf8');
  } catch {
    return false;
  }
  return contentHash(current) === contentHash(shippedContent);
}

/**
 * Resolve the project to install into.
 *
 * npm sets INIT_CWD to the directory the install was started from, which is the
 * project root during a postinstall. Falls back to cwd for a direct CLI call.
 */
function resolveProjectRoot() {
  const candidate = process.env.INIT_CWD || process.cwd();
  return path.resolve(candidate);
}

/** Never install into this package itself, or into a dependency directory. */
function isSelfInstall(projectRoot) {
  if (path.resolve(projectRoot) === PACKAGE_ROOT) return true;
  return projectRoot.split(path.sep).includes('node_modules');
}

function readShipped(relativeSrc) {
  return fs.readFileSync(path.join(PACKAGE_ROOT, relativeSrc), 'utf8');
}

function writeFile(destPath, content, { dryRun }) {
  if (dryRun) return;
  fs.mkdirSync(path.dirname(destPath), { recursive: true });
  fs.writeFileSync(destPath, content, 'utf8');
}

/**
 * Install every framework-owned file. Returns one result row per file so the
 * caller decides how to report it.
 */
function installFrameworkFiles(projectRoot, { dryRun = false } = {}) {
  return FRAMEWORK_FILES.map((file) => {
    const shipped = readShipped(file.src);
    const destPath = path.join(projectRoot, file.dest);
    const existed = fs.existsSync(destPath);
    const unchanged = existed && isPristine(destPath, shipped);

    if (!unchanged) writeFile(destPath, shipped, { dryRun });

    return {
      key: file.key,
      dest: file.dest,
      action: !existed ? 'created' : unchanged ? 'current' : 'updated',
    };
  });
}

/** Seed user-owned files. An existing file is reported and left alone. */
function seedUserFiles(projectRoot, { dryRun = false } = {}) {
  return USER_SEEDS.map((seed) => {
    const destPath = path.join(projectRoot, seed.dest);
    if (fs.existsSync(destPath)) {
      return { key: seed.key, dest: seed.dest, action: 'kept' };
    }
    writeFile(destPath, seed.build(projectRoot), { dryRun });
    return { key: seed.key, dest: seed.dest, action: 'seeded' };
  });
}

/** The Claude Code command is a thin wrapper; the skill stays the single source. */
function claudeCommandContent() {
  return [
    `Read the full skill at \`.github/skills/${SKILL_NAME}/SKILL.md\` FIRST, then follow its instructions exactly.`,
    '',
    'Prerequisite: a Teams transcript file. The Azure DevOps cross-reference is optional;',
    'without it the minute is still produced and traceability is marked TODO.',
    '',
  ].join('\n');
}

function installClaudeCommand(projectRoot, { dryRun = false } = {}) {
  const dest = path.join('.claude', 'commands', `${SKILL_NAME}.md`);
  const destPath = path.join(projectRoot, dest);
  const content = claudeCommandContent();
  const existed = fs.existsSync(destPath);
  const unchanged = existed && isPristine(destPath, content);

  if (!unchanged) writeFile(destPath, content, { dryRun });

  return { key: 'command', dest, action: !existed ? 'created' : unchanged ? 'current' : 'updated' };
}

function readProjectName(projectRoot) {
  const configPath = path.join(projectRoot, 'qa', 'qa-framework.config.json');
  try {
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    return (config.project && config.project.name) || null;
  } catch {
    return null;
  }
}

/**
 * The seeded overlay is deliberately empty of rules. Shipping the example project's
 * vocabulary as a default would push one project's domain onto every other.
 * `data/domain.example.json` is the worked reference.
 */
function buildDomainSeed(projectRoot) {
  const seed = {
    version: 2,
    layer: 'domain',
    project: readProjectName(projectRoot) || '<nombre del proyecto>',
    description:
      'Overlay de dominio del proyecto. User-owned: ningun upgrade lo sobreescribe. ' +
      'Ver data/domain.example.json en @keber/meeting-minutes para un ejemplo completo.',
    sources: [],
    rules: [],
    people: [],
    allowTerms: [],
    glossary: [],
  };
  return `${JSON.stringify(seed, null, 2)}\n`;
}

function isInstalled(projectRoot) {
  return fs.existsSync(path.join(projectRoot, '.github', 'skills', SKILL_NAME, 'SKILL.md'));
}

module.exports = {
  PACKAGE_ROOT,
  SKILL_NAME,
  FRAMEWORK_FILES,
  USER_SEEDS,
  contentHash,
  isPristine,
  resolveProjectRoot,
  isSelfInstall,
  installFrameworkFiles,
  installClaudeCommand,
  seedUserFiles,
  claudeCommandContent,
  buildDomainSeed,
  readProjectName,
  isInstalled,
};
