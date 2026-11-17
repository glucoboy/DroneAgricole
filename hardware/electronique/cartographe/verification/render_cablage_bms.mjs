// Rendu d'artefact Mermaid local, sans interaction avec une session utilisateur.
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/Utilisateur/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve('hardware/electronique/cartographe');const out=path.join(root,'exports/bms_cablage');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try {
 const page=await browser.newPage({viewport:{width:1800,height:1200},deviceScaleFactor:1});
 await page.setContent('<html><body style="margin:20px;background:white"><div id="schema"></div></body></html>');
 await page.addScriptTag({path:path.join(out,'mermaid.min.js')});
 const source=fs.readFileSync(path.join(root,'cablage_global.mmd'),'utf8');
 const svg=await page.evaluate(async source=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'default',flowchart:{useMaxWidth:false,curve:'linear'}});const r=await mermaid.render('bmsSchema',source);document.getElementById('schema').innerHTML=r.svg;return r.svg;},source);
 fs.writeFileSync(path.join(out,'cablage_global.svg'),svg);
 await page.locator('#schema svg').screenshot({path:path.join(root,'verification/cablage_global_bms.png')});
 const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
 fs.writeFileSync(path.join(root,'verification/rendu_cablage_bms.json'),JSON.stringify({date:'2026-10-05',moteur:'Mermaid10.9.3/Chromium headless',source:'cablage_global.mmd',source_sha256:hash(path.join(root,'cablage_global.mmd')),bibliotheque_sha256:hash(path.join(out,'mermaid.min.js')),svg:'exports/bms_cablage/cablage_global.svg',png:'verification/cablage_global_bms.png',png_sha256:hash(path.join(root,'verification/cablage_global_bms.png')),finalisation_correcte:true},null,2)+'\n');
 console.log('Schéma Mermaid rendu correctement');
} finally {await browser.close();}
