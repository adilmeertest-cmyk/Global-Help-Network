import { readFile, writeFile } from 'node:fs/promises';

const file = new URL('../src/main.tsx', import.meta.url);
let source = await readFile(file, 'utf8');

// The lucide Home icon is unused and conflicts with the local Home page component.
// Keep this idempotent so repeated CI/Vercel builds are safe.
const before = "HeartHandshake, Home, LogIn";
const after = "HeartHandshake, LogIn";

if (source.includes(before)) {
  source = source.replace(before, after);
  await writeFile(file, source, 'utf8');
  console.log('prepare-build: removed conflicting unused Home icon import');
} else {
  console.log('prepare-build: no Home import conflict found');
}
