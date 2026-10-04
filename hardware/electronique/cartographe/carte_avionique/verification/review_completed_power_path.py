"""Read-only physical connectivity after removing narrow tracks in memory."""
import hashlib,json,sys
from pathlib import Path
import pcbnew as p
source=Path(sys.argv[1]).resolve(); original_bytes=source.read_bytes(); net=sys.argv[2]; threshold=float(sys.argv[3])
b=p.LoadBoard(str(source))
fs={f.GetReference():f for f in b.GetFootprints()}
fs['R116'].SetDuplicatePadNumbersAreJumpers(False)
pad=lambda ref,num:next(q for q in fs[ref].Pads() if q.GetNumber()==num)
start=pad(sys.argv[4],sys.argv[5]); end=pad(sys.argv[6],sys.argv[7])
assert start.GetNetname()==net and end.GetNetname()==net, 'Pad net differs from requested net'
b.BuildConnectivity()
initial_connected=end.m_Uuid.AsString() in {x.m_Uuid.AsString() for x in b.GetConnectivity().GetConnectedItems(start)}
xy=lambda v:[round(p.ToMM(v.x)-50,6),round(p.ToMM(v.y)-50,6)]
removed=[]
narrow=[t for t in b.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetNetname()==net and p.ToMM(t.GetWidth()) < threshold]
for t in narrow:
    removed.append({'uuid':t.m_Uuid.AsString(),'width_mm':p.ToMM(t.GetWidth()),'length_mm':p.ToMM(t.GetLength()),'start_mm_local':xy(t.GetStart()),'end_mm_local':xy(t.GetEnd()),'layer':b.GetLayerName(t.GetLayer())})
    b.Remove(t)
b.BuildConnectivity()
connected={x.m_Uuid.AsString() for x in b.GetConnectivity().GetConnectedItems(start)}
result={'source':str(source),'source_sha256':hashlib.sha256(original_bytes).hexdigest(),'source_unchanged':source.read_bytes()==original_bytes,'net':net,'minimum_track_width_mm':threshold,'source_pad':sys.argv[4:6],'destination_pad':sys.argv[6:8],'initial_connected':initial_connected,'passed':initial_connected and end.m_Uuid.AsString() in connected,'removed_tracks':removed,'method':'Fresh pcbnew process; narrow tracks removed only in memory, no SaveBoard. Duplicate-pad jumpers disabled in memory. Vias, pads and filled zones retained. This checks a wide physical path, not current capacity.'}
Path(sys.argv[8]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['net','minimum_track_width_mm','source_pad','destination_pad','passed']}))
