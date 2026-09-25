import { execFileSync } from 'node:child_process';
import { cpSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
execFileSync('npm',['run','build'],{cwd:path.join(root,'editor-pptist'),stdio:'inherit'});
const target=path.join(root,'frontend/public/editor-app');
rmSync(target,{recursive:true,force:true});mkdirSync(target,{recursive:true});
cpSync(path.join(root,'editor-pptist/dist'),target,{recursive:true});
