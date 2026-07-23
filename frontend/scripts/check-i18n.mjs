#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import ts from 'typescript';

const translationFile = path.resolve(process.cwd(), 'src/i18n.ts');
const sourceText = fs.readFileSync(translationFile, 'utf8');
const sourceFile = ts.createSourceFile(
    translationFile,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
);

const failures = [];

function propertyName(property) {
    const { name } = property;
    if (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name)) {
        return name.text;
    }
    failures.push(`Unsupported computed translation property at ${sourceFile.getLineAndCharacterOfPosition(name.getStart()).line + 1}`);
    return null;
}

function objectProperty(object, expectedName, context) {
    if (!ts.isObjectLiteralExpression(object)) {
        failures.push(`${context} must be an object literal`);
        return null;
    }
    const matches = object.properties.filter(
        (property) => ts.isPropertyAssignment(property) && propertyName(property) === expectedName,
    );
    if (matches.length !== 1) {
        failures.push(`${context} must contain exactly one ${expectedName} property; found ${matches.length}`);
        return null;
    }
    return matches[0].initializer;
}

let resourcesNode = null;
function findResources(node) {
    if (
        ts.isPropertyAssignment(node)
        && propertyName(node) === 'resources'
        && ts.isObjectLiteralExpression(node.initializer)
    ) {
        if (resourcesNode) {
            failures.push('Multiple i18n resources objects were found');
        }
        resourcesNode = node.initializer;
    }
    ts.forEachChild(node, findResources);
}
findResources(sourceFile);

if (!resourcesNode) {
    failures.push('The i18n resources object was not found');
}

function parseTranslations(node, locale) {
    const leaves = new Map();

    function visit(object, parentPath) {
        if (!ts.isObjectLiteralExpression(object)) {
            failures.push(`${locale}:${parentPath || '<root>'} must be an object literal`);
            return;
        }
        const names = new Set();
        for (const property of object.properties) {
            if (!ts.isPropertyAssignment(property)) {
                failures.push(`${locale}:${parentPath || '<root>'} contains a non-property translation entry`);
                continue;
            }
            const name = propertyName(property);
            if (name === null) continue;
            const key = parentPath ? `${parentPath}.${name}` : name;
            if (names.has(name)) {
                failures.push(`${locale}:${key} is declared more than once`);
                continue;
            }
            names.add(name);
            const value = property.initializer;
            if (ts.isObjectLiteralExpression(value)) {
                visit(value, key);
            } else if (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) {
                leaves.set(key, value.text);
            } else {
                failures.push(`${locale}:${key} must be a string or nested object`);
            }
        }
    }

    visit(node, '');
    return leaves;
}

function localeTranslations(locale) {
    if (!resourcesNode) return new Map();
    const localeNode = objectProperty(resourcesNode, locale, 'resources');
    if (!localeNode) return new Map();
    const translationNode = objectProperty(localeNode, 'translation', `resources.${locale}`);
    if (!translationNode) return new Map();
    return parseTranslations(translationNode, locale);
}

const english = localeTranslations('en');
const spanish = localeTranslations('es');
const englishKeys = new Set(english.keys());
const spanishKeys = new Set(spanish.keys());
const missingInSpanish = [...englishKeys].filter((key) => !spanishKeys.has(key)).sort();
const missingInEnglish = [...spanishKeys].filter((key) => !englishKeys.has(key)).sort();

if (missingInSpanish.length) {
    failures.push(`English keys missing in Spanish (${missingInSpanish.length}):\n  ${missingInSpanish.join('\n  ')}`);
}
if (missingInEnglish.length) {
    failures.push(`Spanish keys missing in English (${missingInEnglish.length}):\n  ${missingInEnglish.join('\n  ')}`);
}

function interpolationVariables(value) {
    const variables = new Set();
    const interpolation = /{{\s*([A-Za-z0-9_.-]+)(?:\s*,[^}]+)?\s*}}/g;
    for (const match of value.matchAll(interpolation)) variables.add(match[1]);
    return [...variables].sort();
}

const allKeys = new Set([...englishKeys, ...spanishKeys]);
for (const [locale, translations] of [['en', english], ['es', spanish]]) {
    for (const [key, value] of translations) {
        const normalizedValue = value.trim();
        if (!normalizedValue) failures.push(`${locale}:${key} has an empty value`);
        if (allKeys.has(normalizedValue)) {
            failures.push(`${locale}:${key} exposes translation key ${normalizedValue} as its value`);
        }
    }
}

for (const key of [...englishKeys].filter((candidate) => spanishKeys.has(candidate)).sort()) {
    const englishVariables = interpolationVariables(english.get(key));
    const spanishVariables = interpolationVariables(spanish.get(key));
    if (englishVariables.join('\0') !== spanishVariables.join('\0')) {
        failures.push(
            `${key} has mismatched interpolation variables: `
            + `English [${englishVariables.join(', ')}], Spanish [${spanishVariables.join(', ')}]`,
        );
    }
}

console.log(`English translation keys: ${english.size}`);
console.log(`Spanish translation keys: ${spanish.size}`);
console.log(`English keys missing in Spanish: ${missingInSpanish.length}`);
console.log(`Spanish keys missing in English: ${missingInEnglish.length}`);

if (failures.length) {
    console.error(`\ni18n validation failed with ${failures.length} issue(s):`);
    for (const failure of failures) console.error(`- ${failure}`);
    process.exit(1);
}

console.log('i18n translation parity, values, duplicates, and interpolation variables are valid.');
