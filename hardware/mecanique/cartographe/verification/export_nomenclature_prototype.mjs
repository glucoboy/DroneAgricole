// Synchronise le classeur de consultation avec son registre JSON, sans toucher le produit custom.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../../..');
const source = path.join(root, 'hardware/mecanique/cartographe/nomenclature_prototype.json');
const target = path.join(root, 'hardware/mecanique/cartographe/exports/Nomenclature_Prototype_Cartographe.xlsx');
const scratch = path.join(root, 'hardware/mecanique/cartographe/exports/verification_nomenclature_prototype');
await fs.mkdir(scratch, {recursive: true});
const data = JSON.parse(await fs.readFile(source, 'utf8'));
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(target));

if(process.argv.includes('--verify-saved')) {
  const id='ELEC-CONNECTEUR-MANUEL';
  const item=data.items.find(r=>r.id===id);
  const inputRow=data.items.filter(r=>r.sous_systeme===item.sous_systeme).findIndex(r=>r.id===id)+8;
  const outputRow=data.presentation.principaux.indexOf(id)+8;
  const input=wb.worksheets.getItem(item.sous_systeme).getRange(`D${inputRow}`);
  const output=wb.worksheets.getItem('Vue système').getRange(`D${outputRow}`);
  const original=input.values;
  const checks=[];
  for(const [value,expected] of [[7,7],[0,0],[null,'À définir']]) {
    input.values=[[value]];
    wb.recalculate();
    const observed=output.values[0][0];
    checks.push({entree:value,attendu:expected,observe:observed,reussi:observed===expected});
    if(observed!==expected) throw new Error(`Synthèse non recalculée pour ${JSON.stringify(value)}`);
  }
  input.values=original;
  wb.recalculate();
  if(output.values[0][0]!==item.quantite) throw new Error('Valeur de synthèse non restaurée');
  const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30}});
  const first=data.items.filter(r=>r.sous_systeme==='Faisceaux').length+13;
  const previews=[];
  for(const [i,r] of data.liaisons.entries()) {
    if(r.id!=='W16' && r.groupe_physique!=='ELEC-F-M8') continue;
    const range=`A${first+i}:G${first+i}`;
    const img=await wb.render({sheetName:'Faisceaux',range,scale:1.3,format:'png'});
    const preview=path.join(scratch,`apres-${r.id}.png`);
    await fs.writeFile(preview,new Uint8Array(await img.arrayBuffer()));
    previews.push({id:r.id,range,fichier:path.relative(root,preview).replaceAll('\\','/')});
  }
  for(const id of ['MEC-SUPPORT-GNSS','MEC-SUPPORTS-RF','MEC-SUPPORTS-SECURITE','ELEC-PASSEFILS']) {
    const item=data.items.find(r=>r.id===id);
    const row=data.items.filter(r=>r.sous_systeme===item.sous_systeme).findIndex(r=>r.id===id)+8;
    const range=`A${row}:G${row}`;
    const img=await wb.render({sheetName:item.sous_systeme,range,scale:1.3,format:'png'});
    const preview=path.join(scratch,`apres-${id}.png`);
    await fs.writeFile(preview,new Uint8Array(await img.arrayBuffer()));
    previews.push({id,range,fichier:path.relative(root,preview).replaceAll('\\','/')});
  }
  for(const [sheetName,range] of [['Perception','K7:O11'],['Énergie','K13:O20']]) {
    const img=await wb.render({sheetName,range,scale:1.1,format:'png'});
    const preview=path.join(scratch,`apres-masses-${sheetName}.png`);
    await fs.writeFile(preview,new Uint8Array(await img.arrayBuffer()));
    previews.push({id:`masses-${sheetName}`,range,fichier:path.relative(root,preview).replaceAll('\\','/')});
  }
  const result={date_utc:new Date().toISOString(),classeur:target,
    moteur:'Artifact Tool après réimport du XLSX ; variations temporaires uniquement en mémoire, aucun enregistrement.',
    recalcul_quantite:checks,erreurs_formules:errors.ndjson,apercus:previews,
    excel_natif_execute:false};
  await fs.writeFile(path.join(scratch,'controle_relecture_artifact.json'),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify(result));
  process.exit(0);
}

if (process.argv.includes('--preview-charge')) {
  const count=data.items.filter(r=>r.sous_systeme==='Faisceaux').length;
  const index=data.liaisons.findIndex(r=>r.id==='W43');
  if(index<0) throw new Error('Liaison W43 absente');
  const row=count+13+index;
  const preview=await wb.render({sheetName:'Faisceaux',range:`A${row-1}:G${row}`,scale:1.2,format:'png'});
  const previewPath=path.join(scratch,'apres-Charge-W43.png');
  await fs.writeFile(previewPath,new Uint8Array(await preview.arrayBuffer()));
  console.log(JSON.stringify({preview:previewPath}));
  process.exit(0);
}

if (process.argv.includes('--inspect')) {
  const preview = await wb.render({sheetName: 'Vue système', range: 'A7:G22', scale: 1.3, format: 'png'});
  await fs.writeFile(path.join(scratch, 'avant.png'), new Uint8Array(await preview.arrayBuffer()));
  console.log((await wb.inspect({kind:'table', range:"Énergie!A13:N23", tableMaxRows:12, tableMaxCols:7, maxChars:2000})).ndjson);
  for (const [sheetName, range] of [['Vue système','A23:G31'],['Énergie','A7:G23'],['Avionique','A8:G14'],['Perception','A22:G26'],['Sol','A14:G19'],['Faisceaux','A7:G13'],['Options et retraits','A7:G12']]) {
    const img = await wb.render({sheetName, range, scale:1, format:'png'});
    await fs.writeFile(path.join(scratch, `avant-${sheetName}.png`), new Uint8Array(await img.arrayBuffer()));
  }
  console.log(JSON.stringify({preview:path.join(scratch, 'avant.png')}));
  process.exit(0);
}

const itemIds = new Set(data.items.map(r => r.id));
const previous = new Map();
for (const {feuille} of data.presentation.sous_systemes) {
  const s = wb.worksheets.getItem(feuille);
  const ids = s.getRange('A8:A250').values.flat();
  ids.forEach((id, i) => {if(itemIds.has(id)) previous.set(id, {sheet:feuille, row:i+8});});
}
const summary = wb.worksheets.getItem('Vue système');
const summaryRows = new Map();
for(let row=8; row<100; row++) {
  const f=summary.getRange(`B${row}`).formulas[0][0];
  const match=f?.match(/^='((?:[^']|'')+)'!B(\d+)$/);
  if(match) {
    const id=wb.worksheets.getItem(match[1].replaceAll("''", "'")).getRange(`A${match[2]}`).values[0][0];
    summaryRows.set(id,row);
  }
}
function replaceTable(s, name, range, style='TableStyleLight9') {
  const old=s.tables.items.find(t=>t.name===name);
  if(!old) throw new Error(`Table absente : ${s.name}/${name}`);
  old.delete();
  const t=s.tables.add(range,true,name);
  t.style=style; t.showFilterButton=true;
}
const notes = r => [...(r.estimation_cao_candidate ? [`ESTIMATION CAO À VALIDER : ${r.estimation_cao_candidate.contribution_g} g pour ${r.estimation_cao_candidate.quantite_absolue_drone} pièces ; ${r.estimation_cao_candidate.condition} Contribution comprise dans le sous-total candidat.`] : []),...(r.estimation_conditionnelle ? [`ESTIMATION À VALIDER : ${r.estimation_conditionnelle.masse_unitaire_g} g × ${r.estimation_conditionnelle.quantite} = ${r.estimation_conditionnelle.contribution_g} g ; ${r.estimation_conditionnelle.perimetre} ${r.estimation_conditionnelle.condition} Non additionnée au sous-total.`] : []),...(r.probleme_massique ? ['MASSE À COMPLÉTER : '+r.probleme_massique.information_manquante] : []),...r.reserves].join(' ');
const itemMatrix = r => [r.id,r.designation,r.reference_fabricant||'À définir',r.quantite,r.unite,r.statut,
  notes(r),r.perimetre,r.choix||r.achat,r.parent,r.masse_unitaire_g,r.masse_nature,
  r.masse_incluse_dans,r.fabricant||'À définir',r.contribution_connue_g??null,r.sources.join('\n')];
const positions = new Map();
for(const {feuille} of data.presentation.sous_systemes) {
  data.items.filter(r=>r.sous_systeme===feuille).forEach((r,i)=>positions.set(r.id,{sheet:feuille,row:i+8}));
}
if(process.argv.includes('--terminal-only') || process.argv.includes('--terminal-preview')) {
  const editing=process.argv.includes('--terminal-only');
  const changes=['SOL-PC','SOL-POWER'];
  if(editing) {
    for(const id of changes) {
      const item=data.items.find(r=>r.id===id), p=positions.get(id);
      wb.worksheets.getItem(p.sheet).getRange(`A${p.row}:P${p.row}`).values=[itemMatrix(item)];
    }
    wb.recalculate();
    console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:30}})).ndjson);
  }
  const first=Math.min(...changes.map(id=>positions.get(id).row));
  const last=Math.max(...changes.map(id=>positions.get(id).row));
  for(const [sheetName,range,name] of [['Sol',`A${first}:G${last}`,'Sol'],['Vue système','A30:G31','Synthese']]) {
    const img=await wb.render({sheetName,range,scale:1.2,format:'png'});
    await fs.writeFile(path.join(scratch,`${editing?'apres':'avant'}-Terminal-${name}.png`),new Uint8Array(await img.arrayBuffer()));
  }
  console.log((await wb.inspect({kind:'table',range:'Vue système!A30:G30',include:'values,formulas',tableMaxRows:1,tableMaxCols:7,maxChars:1200})).ndjson);
  if(editing) {const out=await SpreadsheetFile.exportXlsx(wb);await out.save(target);}
  console.log(JSON.stringify({classeur:target,postes_modifies:editing?changes:[]}));
  process.exit(0);
}
if(process.argv.includes('--charge-only')) {
  for(const id of ['SOL-CHARGER','SOL-CHARGE-ADAPTER']) {
    const item=data.items.find(r=>r.id===id), p=positions.get(id);
    wb.worksheets.getItem(p.sheet).getRange(`A${p.row}:P${p.row}`).values=[itemMatrix(item)];
  }
  const index=data.liaisons.findIndex(r=>r.id==='W43');
  if(index<0) throw new Error('Liaison W43 absente');
  const row=data.items.filter(r=>r.sous_systeme==='Faisceaux').length+13+index;
  const link=data.liaisons[index], s=wb.worksheets.getItem('Faisceaux');
  s.getRange(`C${row}`).values=[[link.connectique]];
  s.getRange(`G${row}`).values=[[link.adaptation_prototype]];
  wb.recalculate();
  console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:30}})).ndjson);
  for(const [sheetName,range,name] of [['Sol','A14:G19','apres-Sol.png'],['Faisceaux',`A${row-1}:G${row}`,'apres-Charge-W43.png'],['Vue système','A23:G31','apres-Vue système-detail.png']]) {
    const img=await wb.render({sheetName,range,scale:1.2,format:'png'});
    await fs.writeFile(path.join(scratch,name),new Uint8Array(await img.arrayBuffer()));
  }
  const out=await SpreadsheetFile.exportXlsx(wb);
  await out.save(target);
  console.log(JSON.stringify({classeur:target,mode:'charge-only',apercus:scratch}));
  process.exit(0);
}
for(const [index, {feuille:sheetName}] of data.presentation.sous_systemes.entries()) {
  const tableName=`Items${index+1}`;
  const s=wb.worksheets.getItem(sheetName);
  const rows=data.items.filter(r=>r.sous_systeme===sheetName);
  const oldCount=[...previous.values()].filter(p=>p.sheet===sheetName).length;
  const oldEnd=7+oldCount, end=7+rows.length;
  rows.forEach((r,i)=> {
    const old=previous.get(r.id), dest=i+8;
    if(old?.sheet===sheetName && old.row!==dest) {
      s.getRange(`A${dest}:P${dest}`).copyFrom(s.getRange(`A${old.row}:P${old.row}`),'all');
    } else if(old?.sheet!==sheetName) {
      s.getRange(`A${dest}:P${dest}`).copyFrom(s.getRange('A8:P8'),'all');
      s.getRange(`A${dest}:P${dest}`).format.rowHeight=54;
    }
  });
  if(sheetName==='Faisceaux' && oldEnd!==end) {
    const oldHeader=oldEnd+5, newHeader=end+5;
    const oldNote=oldEnd+2, newNote=end+2;
    s.unmergeCells(`A${oldNote}:G${oldNote}`);
    const linkTable=s.tables.items.find(t=>t.name==='Liaisons');
    linkTable.delete();
    for(let row=oldEnd+1;row<=oldHeader+data.liaisons.length;row++) {
      s.getRange(`A${row+(end-oldEnd)}:P${row+(end-oldEnd)}`).copyFrom(s.getRange(`A${row}:P${row}`),'all');
    }
    s.getRange(`A${newHeader+data.liaisons.length+1}:P${oldHeader+data.liaisons.length}`).clear({applyTo:'contents'});
    s.mergeCells(`A${newNote}:G${newNote}`);
    const t=s.tables.add(`A${newHeader}:J${newHeader+data.liaisons.length}`,true,'Liaisons');
    t.style='TableStyleLight9'; t.showFilterButton=true;
  } else if(oldEnd>end) {
    s.getRange(`A${end+1}:P${oldEnd}`).clear({applyTo:'contents'});
  }
  s.getRange(`A8:P${end}`).values=rows.map(itemMatrix);
  if(data.orch_cao_masse_1) {
    s.getRange('K7').values=[['Masse unitaire déclarée [g]']];
    s.getRange('O7').copyFrom(s.getRange('K7'),'all');
    s.getRange('O7').values=[['Contribution disponible [g]']];
    s.getRange('O:O').format.columnWidthPx=150;
    // Décimales facultatives : préserver 0,03 g sans ajouter de zéros de précision.
    s.getRange(`K8:K${end}`).format.numberFormat='0.###';
    s.getRange(`O8:O${end}`).format.numberFormat='0.###';
  }
  for(const [i,r] of rows.entries()) {
    if(r.definition_origine || r.probleme_massique) {
      const range=s.getRange(`A${i+8}:P${i+8}`);
      range.format.wrapText=true;
      const lines=Math.max(Math.ceil(r.reference_fabricant.length/38),Math.ceil(notes(r).length/115));
      range.format.rowHeight=Math.max(70,Math.min(250,lines*14+18));
    }
    if(r.id==='ELEC-CONNECTEUR-MANUEL' || ['ELEC-JETI','ELEC-COMMANDE-JETI','ELEC-F39'].includes(r.id)) {
      const range=s.getRange(`A${i+8}:P${i+8}`);
      range.format.wrapText=true;
      range.format.rowHeight=90;
    }
    if(r.id==='AVI-SSD') {
      const range=s.getRange(`A${i+8}:P${i+8}`);
      range.format.wrapText=true;
      range.format.rowHeight=110;
    }
    if(r.id==='MEC-REFROIDISSEMENT-JETSON') {
      const range=s.getRange(`A${i+8}:P${i+8}`);
      range.format.wrapText=true;
      range.format.rowHeight=90;
    }
    if(r.id==='SEN-LENS' || r.id==='SOL-PC') {
      const range=s.getRange(`A${i+8}:P${i+8}`);
      range.format.wrapText=true;
      range.format.rowHeight=110;
    }
    if(r.id==='SOL-CHARGER' || r.id==='SOL-CHARGE-ADAPTER') {
      const range=s.getRange(`A${i+8}:P${i+8}`);
      range.format.wrapText=true;
      range.format.rowHeight=110;
    }
  }
  s.getRange('D5').formulas=[[`=COUNTA(A8:A${end})`]];
  replaceTable(s,tableName,`A7:N${end}`);
  if(sheetName==='Faisceaux') {
    const first=end+6;
    s.getRange(`A${first}:P${first+data.liaisons.length-1}`).values=data.liaisons.map(r=>[
      r.id,r.fonction,r.connectique,r.quantite_faisceaux,r.longueur_m,r.statut,r.adaptation_prototype,
      r.de,r.vers,r.groupe_physique,null,null,null,null,null,r.source]);
    for(const [i,r] of data.liaisons.entries()) {
      if(['W16','W-M8','W43'].includes(r.id) || r.groupe_physique==='ELEC-F-M8') {
        const range=s.getRange(`A${first+i}:P${first+i}`);
        range.format.wrapText=true;
        const lines=Math.max(Math.ceil(r.connectique.length/38),Math.ceil(r.adaptation_prototype.length/115));
        range.format.rowHeight=Math.max(90,Math.min(300,lines*14+18));
      }
    }
  }
}
const main=data.presentation.principaux;
main.forEach((id,i)=> {
  const old=summaryRows.get(id), row=i+8;
  if(old!==row) summary.getRange(`A${row}:G${row}`).copyFrom(summary.getRange(`A${old}:G${old}`),'all');
});
if(summaryRows.size>main.length) summary.getRange(`A${8+main.length}:G${7+summaryRows.size}`).clear({applyTo:'contents'});
main.forEach((id,i)=> {
  const r=data.items.find(r=>r.id===id), row=i+8, p=positions.get(id);
  const ref="'"+p.sheet.replaceAll("'", "''")+"'";
  summary.getRange(`A${row}:G${row}`).values=[[r.sous_systeme,null,null,null,null,
    r.perimetre==='sol'?'Au sol':r.perimetre==='approvisionnement'?'Lot : inclusions à lire':'Embarqué',`${p.sheet} · ${p.row}`]];
  for(const col of ['B','C','E']) summary.getRange(`${col}${row}`).formulas=[[`=${ref}!${col}${p.row}`]];
  summary.getRange(`D${row}`).formulas=[[`=IF(ISNUMBER(${ref}!D${p.row}),${ref}!D${p.row},"À définir")`]];
});
replaceTable(summary,'VueSysteme',`A7:G${7+main.length}`);
summary.getRange('A4').values=[['X650 + sélection actuelle • Branchement = marche ; débranchement = arrêt, sans JETI ni fast-swap.']];
summary.getRange('A4').format.rowHeight=32;
if(data.orch_cao_masse_1) {
  summary.getRange('A4').values=[['ORCH-CAO-MASSE-1 · Masse complète inconnue. Contributions disponibles en colonne O ; calculs candidats et conditions dans le JSON canonique.']];
  summary.getRange('A4').format.wrapText=true;
  summary.getRange('A4').format.rowHeight=36;
}
const connectorRow=main.indexOf('ELEC-CONNECTEUR-MANUEL')+8;
summary.getRange(`A${connectorRow}:G${connectorRow}`).format.rowHeight=54;
const pcRow=main.indexOf('SOL-PC')+8;
summary.getRange(`A${pcRow}:G${pcRow}`).format.rowHeight=80;
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Vue système!A23:G31',include:'values,formulas',tableMaxRows:9,tableMaxCols:5,maxChars:1800})).ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',
  options:{useRegex:true,maxResults:30},summary:'Erreurs du classeur après synchronisation'});
console.log(errors.ndjson);
for(const [sheetName,range] of [['Vue système','A7:G22'],['Structure','A7:G11'],['Propulsion','A7:G12'],['Énergie','A8:G12'],['Avionique','A8:G10'],['CA01','A7:G9'],['Perception','A17:G24'],['Navigation et radio','A7:G13'],['Sol','A8:G14'],['Faisceaux','A7:G12'],['Options et retraits','A7:G10']]) {
  const img=await wb.render({sheetName,range,scale:1.2,format:'png'});
  await fs.writeFile(path.join(scratch,`apres-${sheetName}.png`),new Uint8Array(await img.arrayBuffer()));
}
const summaryDetail=await wb.render({sheetName:'Vue système',range:'A23:G31',scale:1.2,format:'png'});
await fs.writeFile(path.join(scratch,'apres-Vue système-detail.png'),new Uint8Array(await summaryDetail.arrayBuffer()));
for(const id of ['ELEC-F16','ELEC-F-M8','ELEC-COLLIERS','MEC-BATTERIE-SUPPORT','MEC-BATTERIE-FIXATIONS','MEC-SUPPORTS-ENERGIE','MEC-SUPPORT-AVIONIQUE']) {
  const p=positions.get(id);
  if(!p) throw new Error(`Poste de vérification absent : ${id}`);
  const img=await wb.render({sheetName:p.sheet,range:`A${p.row}:G${p.row}`,scale:1.3,format:'png'});
  await fs.writeFile(path.join(scratch,`apres-${id}.png`),new Uint8Array(await img.arrayBuffer()));
}
const controls=[];
for(const r of data.items) {
  const p=positions.get(r.id);
  const actual=wb.worksheets.getItem(p.sheet).getRange(`A${p.row}:P${p.row}`).values[0];
  const expected=itemMatrix(r);
  if(actual.some((value,i)=>(value??null)!==(expected[i]??null))) throw new Error(`Poste exporté divergent : ${r.id}`);
}
controls.push({controle:'postes_fideles',reussi:true,nombre:data.items.length});
const linkFirst=data.items.filter(r=>r.sous_systeme==='Faisceaux').length+13;
for(const [i,r] of data.liaisons.entries()) {
  const actual=wb.worksheets.getItem('Faisceaux').getRange(`A${linkFirst+i}:J${linkFirst+i}`).values[0];
  const expected=[r.id,r.fonction,r.connectique,r.quantite_faisceaux,r.longueur_m,r.statut,r.adaptation_prototype,r.de,r.vers,r.groupe_physique];
  if(actual.some((value,j)=>(value??null)!==(expected[j]??null))) throw new Error(`Liaison exportée divergente : ${r.id}`);
}
controls.push({controle:'liaisons_fideles',reussi:true,nombre:data.liaisons.length});
await fs.writeFile(path.join(scratch,'controle_export_artifact.json'),JSON.stringify({
  date_utc:new Date().toISOString(),portee:'Export de consultation de la définition candidate ; aucune validation de la CAO ou qualification physique.',
  details_encore_a_terminer:data.resolution_definition.details_encore_a_terminer.length,
  controles:controls,erreurs_formules:errors.ndjson,
  points_verifies:['ELEC-F16','ELEC-F-M8','ELEC-COLLIERS'].map(id=>({id,...positions.get(id)}))
},null,2)+'\n');
const out=await SpreadsheetFile.exportXlsx(wb);
await out.save(target);
console.log(JSON.stringify({classeur:target,principaux:main.length,postes:data.items.length,apercus:scratch}));
