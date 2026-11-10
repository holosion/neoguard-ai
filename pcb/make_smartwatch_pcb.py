import pcbnew as p
from pathlib import Path
root=Path('pcb'); board=p.LoadBoard(str(root/'NeoGuard.kicad_pcb')); lib=Path(r'C:/Program Files/KiCad/10.0/share/kicad/footprints')
new=[('U1','RF_Module:ESP32-S3-WROOM-1',(95,55),0),('J10','Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',(95,112),0),('U3','Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.6x1.6mm',(115,92),0),('U4','Package_SON:Texas_DRC0010J_ThermalVias',(130,92),0),('BT1','Battery:BatteryHolder_Keystone_1042_1x12mm',(65,105),0),('L1','Inductor_SMD:L_4.0x4.0mm_L4.0-W4.0',(130,102),0),('R10','Resistor_SMD:R_0603_1608Metric',(105,100),0),('R11','Resistor_SMD:R_0603_1608Metric',(110,100),0),('R12','Resistor_SMD:R_0603_1608Metric',(115,100),0),('R13','Resistor_SMD:R_0603_1608Metric',(120,100),0),('R14','Resistor_SMD:R_0603_1608Metric',(125,100),0),('C10','Capacitor_SMD:C_0603_1608Metric',(105,105),0),('C11','Capacitor_SMD:C_0603_1608Metric',(110,105),0),('C12','Capacitor_SMD:C_0603_1608Metric',(115,105),0),('C13','Capacitor_SMD:C_0603_1608Metric',(120,105),0)]
for ref,fp,pos,rot in new:
 if any(x.GetReference()==ref for x in board.GetFootprints()): continue
 libn,name=fp.split(':'); f=p.FootprintLoad(str(lib/(libn+'.pretty')),name)
 if not f: print('missing',fp); continue
 f.SetReference(ref); f.SetValue(ref); f.SetPosition(p.VECTOR2I(round(pos[0]*1e6),round(pos[1]*1e6))); f.SetOrientationDegrees(rot); f.Reference().SetVisible(True); board.Add(f)
for d in list(board.GetDrawings()):
 if isinstance(d,p.PCB_TEXT) and ('LCD' in d.GetText() or 'CARRIER' in d.GetText()): board.Delete(d)
def label(s,x,y,size=1.0):
 t=p.PCB_TEXT(board);t.SetText(s);t.SetLayer(p.F_SilkS);t.SetPosition(p.VECTOR2I(round(x*1e6),round(y*1e6)));t.SetTextSize(p.VECTOR2I(round(size*1e6),round(size*1e6)));t.SetTextThickness(round(.14e6));board.Add(t)
label('AKENA NEOGUARD | SMARTWATCH POWER + ESP32-S3',90,25,1.25); label('USB-C CHARGE | 1S LiPo | 3V3 REGULATED',90,121,.9); label('ESP32-S3-WROOM-1',95,46,1.0); label('BQ24074 CHARGER',115,87,.8); label('TPS63001 3V3',130,87,.8); label('LiPo CELL',65,99,.8); label('USB-C',95,118,.8)
board.GetTitleBlock().SetRevision('E-POWER'); board.GetTitleBlock().SetTitle('NeoGuard smartwatch-style ESP32-S3 power revision')
p.SaveBoard(str(root/'NeoGuard-smartwatch.kicad_pcb'),board); print('saved')
