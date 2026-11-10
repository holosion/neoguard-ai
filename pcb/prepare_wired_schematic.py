"""Prepare revision E schematic work without changing the checked revision D PCB."""
from pathlib import Path
import shutil,json
root=Path(__file__).resolve().parent
out=root/'schematic-revision-e'
out.mkdir(exist_ok=True)
for name in ['design_manifest.json','NeoGuard.kicad_pro','fp-lib-table']:
    if not (out/name).exists():shutil.copy2(root/name,out/name)
s=(root.parent/'schematic/build_schematic_rev_b.py').read_text()
s=s.replace('2026-10-21','2026-10-29').replace('(rev "B")','(rev "E-DRAFT")')
a=s.index('u1ps=[]')
s=s[:a]+'''# Show every unused external GPIO and mark its endpoint with an X.
unused=[str(n) for n in list(range(22))+list(range(35,49)) if str(n) not in U1NET]+['EN','5V']
for i,n in enumerate(unused):
    left=i<10
    GPINS.append((n,'GPIO'+n if n.isdigit() else n,147.38 if left else 232.62,87.63+i*5.08 if left else 143.51+(i-10)*5.08,0 if left else 180,'passive'))
    U1NET[n]=None
''' +s[a:]
s=s.replace("for n in U1NET:\n    p=", "for n in U1NET:\n    if U1NET[n] is None:continue\n    p=")
s=s.replace('Offboard controller\\nGPIO labels shown, not\\nphysical header positions.\\n\\nNative USB stays on\\nthe development board.\\n\\nBuilt-in Wi-Fi connects\\nto the HTTPS backend.', 'Logical GPIO interface\\nExternal connections\\nX = unused carrier pin')
s=s.replace("',163,116,1.15)","',163,169,1.0)")
s=s.replace('Pins 1 and 21-24 are common ground returns.','Pins 1, 21, 23, 24 are ground; pin22 is unused.')
s=s.replace('if ref=="U1" else','if ref=="U1" or ref.startswith("#") else')
# Real GND symbols, attached by visible wires at each ground connection.
s=s.replace("    def label(self,net,p,angle=0):\n        p=sp(p);", """    def label(self,net,p,angle=0):
        if net=='GND':
            p=sp(p);q=p
            name='GND';LIBS[name]=libsym('power',name)
            ref='#PWR'+str(1000+len(PLACED))
            CM[ref]={'value':'GND','footprint':'','pins':{'1':'GND'},'symbol':'power:GND'}
            self.place(ref,*q,libname='GND')
            return
        p=sp(p);""")
# Ground references are hidden, as expected for conventional power symbols.
s=s.replace('props=f\'(property "Reference" "{ref}" (at {rx} {ry} {a}) {eff(1.25)})', 'props=f\'(property "Reference" "{ref}" (at {rx} {ry} {a}) {eff(1.25,hide=ref.startswith("#"))})')
# Mark this standalone schematic explicitly until charging/display choices are fixed.
s=s.replace('Every used GPIO is drawn to its peripheral. Module blocks represent the carrier cable interfaces.', 'DRAFT E: direct signal wiring and ground symbols. USB-C battery power design is pending the battery specification.')
s=s.replace("print('Revision B schematic written: 26 carrier parts + offboard U1, two sheets, 119 pins including 1 NC.')", "print('Wrote revision E wired schematic draft.')")
a=s.index("main.save('NeoGuard.kicad_sch'")
s=s[:a]+"""LIBS['PWR_FLAG']=libsym('power','PWR_FLAG')
CM['#FLG01']={'value':'PWR_FLAG','footprint':'','pins':{'1':'GND'},'symbol':'power:PWR_FLAG'}
power.place('#FLG01',210,230,libname='PWR_FLAG',autolabel=True)

"""+s[a:]
(out/'build_schematic.py').write_text(s)
(out/'README.md').write_text('''# Revision E schematic work

This is the schematic-first redesign requested on 29 October 2026. It draws direct signal wires between the ESP32-S3 and peripherals, retains unused-pin X marks, and adds conventional ground symbols.

USB-C charging, the battery specification, exact display module and controller mounting are still being resolved. Do not fabricate this draft. The checked revision D board in the parent folder remains a different design.
''')
print(out)
