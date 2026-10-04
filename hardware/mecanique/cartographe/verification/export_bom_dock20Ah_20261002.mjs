// Export de la nomenclature technique JSON vers un classeur consultable.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../../../..');
const out=path.join(root,'outputs/dock20Ah_20261002');
const bom=JSON.parse(await fs.readFile(path.join(here,'bom_dock20Ah_20261002.json'),'utf8'));
if(bom.anomalies_generation?.length) throw new Error(JSON.stringify(bom.anomalies_generation));
const wb=Workbook.create();
const font='Arial';
function sheet(name,title,header,rows,widths,context) {
  const s=wb.worksheets.add(name);s.showGridLines=false;
  const last=String.fromCharCode(64+header.length);
  const end=5+rows.length;
  s.getRange(`A1:${last}${end}`).format.font={name:font,size:10,color:'#24303c'};
  s.getRange('A2').values=[[title]];s.getRange('A2').format.font={name:font,size:14,bold:true};
  s.getRange(`A2:${last}2`).format.borders={bottom:{style:'thin',color:'#526b7c'}};
  s.getRange('A3').values=[[context]];s.getRange('A3').format.font={name:font,size:10,color:'#66552b'};
  s.getRange('A4').values=[[name==='Achats'?'XT90 : 45 A catalogue sous conditions. Kit JETI 8 mm² à confirmer. Échange après OFF manuel.':'Prototype à valider. Budget partiel avec provisions : 6,11–6,73 kg ; limite X650 publiée : 6,3 kg.']];
  s.getRange('A4').format.font={name:font,size:9,color:'#9a402e'};
  s.getRange(`A5:${last}5`).values=[header];
  s.getRange(`A5:${last}5`).format={fill:'#314f64',font:{name:font,size:10,bold:true,color:'#ffffff'},
    horizontalAlignment:'center',verticalAlignment:'center',rowHeight:27};
  s.getRange(`A6:${last}${end}`).values=rows;
  s.getRange(`A6:${last}${end}`).format={wrapText:true,verticalAlignment:'center',rowHeight:42};
  s.getRange(`A6:A${end}`).format.numberFormat='0';
  s.getRange(`A6:A${end}`).format.horizontalAlignment='right';
  widths.forEach((w,i)=>s.getRange(`${String.fromCharCode(65+i)}5:${String.fromCharCode(65+i)}${end}`).format.columnWidth=w);
  for(let i=0;i<rows.length;i++)if(i%2===1)s.getRange(`A${6+i}:${last}${6+i}`).format.fill='#f1f4f6';
  s.freezePanes.freezeRows(5);s.freezePanes.freezeColumns(2);
  s.tables.add(`A5:${last}${end}`,true,name+'Liste');
  return s;
}
const spec=r=>r.specification_native || r.matiere_native || '';
sheet('Fabrication','Pièces du dock 6S 20 Ah',
  ['Qté','Référence CAO','Matière et fabrication','Validation physique'],
  bom.pieces_fabriquees.map(r=>[r.quantite_installee,r.reference,spec(r),'À valider']),
  [7,48,62,20], 'Un drone et une cassette. Les pièces du drone conservées sont dans le manifeste général.');
sheet('Achats','Composants du commerce',
  ['Qté installée','Qté à acheter','Fabricant','Référence fabricant','Désignation','Validation physique','Source'],
  bom.composants_commerce.map(r=>[r.quantite_installee,r.quantite_achat_unitaire,r.fabricant||'',r.mpn||'',r.designation||'','À valider',r.source||'']),
  [12,12,18,32,58,20,74], 'Quantités pour un drone et une cassette. Les composants inclus dans un kit ne sont pas rachetés.');
sheet('Visserie','Visserie de la nouvelle intégration',
  ['Qté','Référence','Standard et matière','Validation physique'],
  bom.visserie_modelee.map(r=>[r.quantite_installee,r.reference,spec(r),'À valider']),
  [7,49,65,20], 'Les modèles simplifient les filets. Vérifier les références et serrages de la BOM technique.');
wb.recalculate();
await fs.mkdir(out,{recursive:true});
for(const name of ['Fabrication','Achats','Visserie']) {
  const b=await wb.render({sheetName:name,range:name==='Achats'?'A1:F13':'A1:D13',scale:1.4,format:'png'});
  await fs.writeFile(path.join(out,'apercu_'+name+'.png'),new Uint8Array(await b.arrayBuffer()));
  const lastRange={Fabrication:'A23:D32',Achats:'A20:F30',Visserie:'A31:D39'}[name];
  const tail=await wb.render({sheetName:name,range:lastRange,scale:1.4,format:'png'});
  await fs.writeFile(path.join(out,'apercu_fin_'+name+'.png'),new Uint8Array(await tail.arrayBuffer()));
}
const check=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',
  options:{useRegex:true,maxResults:30},summary:'Contrôle du classeur BOM'});
console.log(check.ndjson);
const x=await SpreadsheetFile.exportXlsx(wb);
await x.save(path.join(out,'BOM_Dock20Ah.xlsx'));
await fs.writeFile(path.join(here,'export_bom_dock20Ah_20261002.json'),JSON.stringify({
  date:'2026-10-03',source:'bom_dock20Ah_20261002.json',classeur:'outputs/dock20Ah_20261002/BOM_Dock20Ah.xlsx',
  source_sha256:createHash('sha256').update(await fs.readFile(path.join(here,'bom_dock20Ah_20261002.json'))).digest('hex'),
  classeur_sha256:createHash('sha256').update(await fs.readFile(path.join(out,'BOM_Dock20Ah.xlsx'))).digest('hex'),
  lignes:{Fabrication:bom.pieces_fabriquees.length,Achats:bom.composants_commerce.length,Visserie:bom.visserie_modelee.length},
  feuilles:['Fabrication','Achats','Visserie'],controles:'Quantités issues de la BOM JSON ; rendu et scan des erreurs ; aucune qualification Excel native.'},null,2)+'\n');
console.log(path.join(out,'BOM_Dock20Ah.xlsx'));
