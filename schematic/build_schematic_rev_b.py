"""NeoGuard revision B: explicit ESP32 GPIO wiring and separate carrier power sheet."""
from pathlib import Path
import json, re, math, uuid, copy

ROOT=Path(__file__).resolve().parent
LIBROOT=Path(r'C:\Program Files\KiCad\10.0\share\kicad\symbols')
M=json.loads((ROOT/'design_manifest.json').read_text())
CM={c['ref']:c for c in M['components']}
NS=uuid.UUID('d620ef9a-1167-4b36-a1d1-cfb663e4d101')
def uid(s): return str(uuid.uuid5(NS,s))
def snap(v):return round(round(v/1.27)*1.27,4)
def sp(p):return (snap(p[0]),snap(p[1]))
RID=uid('schematic-root'); SID=uid('power-sheet-instance'); CID=uid('schematic-power')
class Atom(str): pass
def parse(src):
    toks=re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',src);i=0
    def one():
        nonlocal i
        t=toks[i];i+=1
        if t=='(':
            o=[]
            while toks[i]!=')':o.append(one())
            i+=1;return o
        return json.loads(t) if t.startswith('"') else Atom(t)
    return one()
def dump(v):
    if isinstance(v,list):return '('+' '.join(dump(x) for x in v)+')'
    return str(v) if isinstance(v,Atom) else json.dumps(v,ensure_ascii=False)
def child(v,k):return next((x for x in v[1:] if isinstance(x,list) and x[0]==k),None)
def children(v,k):return [x for x in v[1:] if isinstance(x,list) and x[0]==k]
def rename(v,old,new):
    if isinstance(v,list):
        if len(v)>1 and v[0]=='symbol' and str(v[1]).startswith(old+'_'):v[1]=new+v[1][len(old):]
        for x in v:rename(x,old,new)
CACHE={}
def libsym(lib,name):
    if lib not in CACHE:
        t=parse((LIBROOT/(lib+'.kicad_sym')).read_text(encoding='utf-8'))
        CACHE[lib]={str(x[1]):x for x in children(t,'symbol')}
    s=copy.deepcopy(CACHE[lib][name]);e=child(s,'extends')
    if e:
        b=libsym(lib,str(e[1]));rename(b,str(b[1]),name);b[1]=name
        props={str(p[1]):p for p in children(b,'property')}
        props.update({str(p[1]):p for p in children(s,'property')})
        b=[x for x in b if not(isinstance(x,list) and x[0]=='property')];b.extend(props.values());s=b
    return s
def eff(size=1,justify='',hide=False,bold=False):
    return f'(effects (font (size {size} {size}) '+('bold' if bold else '')+') '+(f'(justify {justify}) ' if justify else '')+('hide' if hide else '')+')'
LIBS={}
for c in M['components']:
    lib,name=c['symbol'].split(':')
    if name not in LIBS:LIBS[name]=libsym(lib,name)

def custom_module(name,width,top,bottom,pins,side='right'):
    """Functional module interface, with actual carrier connector pad numbers."""
    body=f'(symbol "{name}_0_1" (rectangle (start {-snap(width/2)} {snap(top)}) (end {snap(width/2)} {snap(bottom)}) (stroke (width 0.254) (type default)) (fill (type background))))'
    ps=[]
    for n,pname,yy in pins:
        xx=(snap(width/2)+7.62) if side=='right' else (-snap(width/2)-7.62)
        ang=180 if side=='right' else 0
        hide='hide' if pname=='Pin_5' else ''
        ps.append(f'(pin passive line (at {xx} {yy} {ang}) (length 7.62) (name {json.dumps(pname)} (effects (font (size 1.05 1.05)) {hide})) (number "{n}" {eff(1.0)}))')
    s=f'(symbol "{name}" (pin_names (offset 1.27)) (in_bom yes) (on_board yes) (property "Reference" "J" (at 0 {top+3.81} 0) {eff(1.27)}) (property "Value" "{name}" (at 0 {bottom-3.81} 0) {eff(1.27)}) {body} (symbol "{name}_1_1" '+''.join(ps)+'))'
    LIBS[name]=parse(s)

# Absolute page coordinates are converted into each functional connector's local coordinates.
MODS={
 'J2':('MAX30102_Interface',50,62.5,50,23,-22,[('1','VCC',50),('2','GND',55),('3','SDA',70),('4','SCL',75),('5','Pin_5',80)],'right'),
 'J3':('MLX90614_Interface',50,105,50,16,-14,[('1','VCC',95),('2','GND',100),('3','SDA',110),('4','SCL',115)],'right'),
 'J4':('DS1302_Interface',50,145,50,20,-20,[('1','VCC',132),('2','GND',137),('3','CLK',147),('4','DAT',152),('5','CE / RST',157)],'right'),
 'J7':('RGB_Interface',50,200,50,17,-22,[('1','RED A',195),('2','GREEN A',200),('3','BLUE A',205),('4','COMMON K',215)],'right'),
 'J5':('ST7789_Interface',350,77.5,50,25,-27,[('1','GND',90),('2','VCC',95),('3','SCK',80),('4','MOSI',75),('5','RST',60),('6','DC',65),('7','CS',70),('8','BL / BLK',100)],'left'),
 'J6':('MicroSD_Interface',350,137.5,50,25,-27,[('1','VCC',155),('2','GND',160),('3','SCK',125),('4','MOSI',130),('5','MISO',135),('6','CS',120)],'left'),
 'J8':('Buzzer_Interface',357.5,180,35,15,-15,[('1','POSITIVE',175),('2','NEGATIVE',185)],'left')
}
for ref,(name,x,y,w,t,b,pins,side) in MODS.items():
    custom_module(name,w,t,b,[(n,pn,round(snap(y)-snap(yy),4)) for n,pn,yy in pins],side)

GPINS=[
 ('4','GPIO4 / SDA',147.38,70,0,'bidirectional'),('5','GPIO5 / SCL',147.38,75,0,'bidirectional'),
 ('6','GPIO6 / CLK',147.38,147,0,'output'),('7','GPIO7 / DAT',147.38,152,0,'bidirectional'),('14','GPIO14 / CE',147.38,157,0,'output'),
 ('16','GPIO16 / RED',147.38,195,0,'output'),('17','GPIO17 / GREEN',147.38,200,0,'output'),('18','GPIO18 / BLUE',147.38,205,0,'output'),
 ('8','GPIO8 / RST',232.62,60,180,'output'),('9','GPIO9 / DC',232.62,65,180,'output'),('10','GPIO10 / CS',232.62,70,180,'output'),('11','GPIO11 / MOSI',232.62,75,180,'output'),('12','GPIO12 / SCK',232.62,80,180,'output'),
 ('21','GPIO21 / CS',232.62,120,180,'output'),('40','GPIO40 / SCK',232.62,125,180,'output'),('41','GPIO41 / MOSI',232.62,130,180,'output'),('42','GPIO42 / MISO',232.62,135,180,'input'),
 ('15','GPIO15 / BUZZ',232.62,200,180,'output'),('3V3','3V3 OUT',175,40.38,270,'passive'),('GND','GND',190,232.62,90,'passive')
]
U1NET={'4':'I2C_SDA_GPIO4','5':'I2C_SCL_GPIO5','6':'RTC_CLK_GPIO6','7':'RTC_DAT_GPIO7','14':'RTC_CE_GPIO14','16':'LED_R_GPIO16','17':'LED_G_GPIO17','18':'LED_B_GPIO18','8':'TFT_RST_GPIO8','9':'TFT_DC_GPIO9','10':'TFT_CS_GPIO10','11':'TFT_MOSI_GPIO11','12':'TFT_SCK_GPIO12','21':'SD_CS_GPIO21','40':'SD_SCK_GPIO40','41':'SD_MOSI_GPIO41','42':'SD_MISO_GPIO42','15':'BUZZ_GPIO15','3V3':'DEV3V3','GND':'GND'}
u1ps=[]
for n,pn,x,y,a,typ in GPINS:
    u1ps.append(f'(pin {typ} line (at {round(snap(x)-snap(190),4)} {round(snap(136.5)-snap(y),4)} {a}) (length 7.62) (name {json.dumps(pn)} {eff(1.05)}) (number "{n}" {eff(1.0)}))')
LIBS['ESP32_S3_Logical']=parse('(symbol "ESP32_S3_Logical" (pin_names (offset 1.27)) (in_bom no) (on_board no) (property "Reference" "U" (at 0 92 0) '+eff(1.5)+') (property "Value" "ESP32-S3 DEVELOPMENT BOARD" (at 0 87 0) '+eff(1.5)+') (symbol "ESP32_S3_Logical_0_1" (rectangle (start -35.56 88.9) (end 34.29 -87.63) (stroke (width 0.508) (type default)) (fill (type background)))) (symbol "ESP32_S3_Logical_1_1" '+''.join(u1ps)+'))')

def pin_defs(s):
    out=[]
    for sub in children(s,'symbol'):
        for p in children(sub,'pin'):
            at=child(p,'at');n=child(p,'number');out.append((str(n[1]),float(at[1]),float(at[2]),float(at[3])))
    return out
def pos(x,y,a,px,py):
    r=math.radians(a)
    return (round(x+px*math.cos(r)-py*math.sin(r),4),round(y-px*math.sin(r)-py*math.cos(r),4))

PLACED={};PATHS={};ALLPINS={}
class Page:
    def __init__(self,key,instpath):self.key=key;self.path=instpath;self.items=[];self.pins={}
    def add(self,s):self.items.append(s)
    def oid(self,kind):return uid(self.key+'-'+kind+'-'+str(len(self.items)))
    def text(self,s,x,y,size=1.1,bold=False):self.add(f'(text {json.dumps(s)} (at {x} {y} 0) {eff(size,"left top",bold=bold)} (uuid {self.oid("text")}))')
    def wire(self,a,b):
        a=sp(a);b=sp(b)
        if a!=b:self.add(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {self.oid("wire")}))')
    def pathwire(self,*pts):
        for a,b in zip(pts,pts[1:]):self.wire(a,b)
    def dot(self,p):
        p=sp(p);self.add(f'(junction (at {p[0]} {p[1]}) (diameter 0) (color 0 0 0 0) (uuid {self.oid("dot")}))')
    def label(self,net,p,angle=0):
        p=sp(p);self.add(f'(global_label {json.dumps(net)} (shape passive) (at {p[0]} {p[1]} {angle}) {eff(.95,"left")} (uuid {self.oid("glabel")}))')
    def place(self,ref,x,y,a=0,libname=None,showval=False,autolabel=False):
        x=snap(x);y=snap(y)
        c=CM[ref] if ref!='U1' else {'value':'ESP32-S3 DEVELOPMENT BOARD','footprint':'','pins':U1NET}
        name=libname or c['symbol'].split(':')[1];s=LIBS[name];sid=uid('instance-'+ref)
        PLACED[ref]=sid;PATHS[ref]=self.path+'/'+sid
        rx=x;ry=y-7;vx=x;vy=y-10
        if a in(90,270):rx=x-5;vx=x+5;ry=vy=y-3.5
        if ref=='U1':ry=43;vy=37
        props=f'(property "Reference" "{ref}" (at {rx} {ry} {a}) {eff(1.25)}) (property "Value" {json.dumps(c["value"])} (at {vx} {vy} {a}) {eff(1,"",not showval)}) (property "Footprint" {json.dumps(c["footprint"])} (at {x} {y} 0) {eff(1,"",True)})'
        ps=''
        for n,px,py,pa in pin_defs(s):
            pt=pos(x,y,a,px,py);self.pins[(ref,n)]=pt;ALLPINS[(ref,n)]=pt
            ps+=f'(pin "{n}" (uuid {uid(ref+"-pin-"+n)}))'
            net=c['pins'][n]
            if net is None:self.add(f'(no_connect (at {pt[0]} {pt[1]}) (uuid {uid(ref+"-nc-"+n)}))')
            elif autolabel:
                rr=math.radians(a+pa)
                length=20.32 if ref=='J1' else 10.16
                q=(round(pt[0]-length*math.cos(rr),4),round(pt[1]+length*math.sin(rr),4))
                self.wire(pt,q);self.label(net,q,0 if math.cos(rr)<-.1 else 180)
        self.add(f'(symbol (lib_id "NeoGuard:{name}") (at {x} {y} {a}) (unit 1) (in_bom {"no" if ref=="U1" else "yes"}) (on_board {"no" if ref=="U1" else "yes"}) (dnp {"yes" if c.get("dnp") else "no"}) (uuid {sid}) {props} {ps} (instances (project "NeoGuard" (path "{self.path}" (reference "{ref}") (unit 1)))))')
    def p(self,ref,n):return self.pins[(ref,str(n))]
    def netstub(self,ref,n,delta=(5.08,0),angle=0):
        p=self.p(ref,n);q=(round(p[0]+delta[0],4),round(p[1]+delta[1],4));self.wire(p,q)
        c=CM[ref] if ref!='U1' else {'pins':U1NET};self.label(c['pins'][str(n)],q,angle)
    def save(self,filename,title,uuid_,page):
        defs=[]
        for name,s in LIBS.items():
            s=copy.deepcopy(s);s[1]='NeoGuard:'+name;defs.append(dump(s))
        head=f'(kicad_sch (version 20250114) (generator "neoguard_design") (uuid {uuid_}) (paper "A3") (title_block (title {json.dumps(title)}) (date "2026-10-21") (rev "B") (company "NeoGuard research prototype") (comment 1 "GPIO names are logical signals; verify actual module headers and voltages")) (lib_symbols '+''.join(defs)+')\n'
        tail=f'(sheet_instances (path "/" (page "{page}")))' if page==1 else ''
        (ROOT/filename).write_text(head+'\n'.join(self.items)+'\n'+tail+' (embedded_fonts no))\n',encoding='utf-8')

main=Page('main','/'+RID)
main.text('NEOGUARD | ESP32-S3 SYSTEM CONNECTIONS',15,14,2.3,True)
main.text('Every used GPIO is drawn to its peripheral. Module blocks represent the carrier cable interfaces.',15,22,1.15)
main.place('U1',190,136.5,libname='ESP32_S3_Logical')
main.text('ESP32-S3',171,98,2.5,True)
main.text('DEVELOPMENT BOARD',165,106,1.4,True)
main.text('Offboard controller\nGPIO labels shown, not\nphysical header positions.\n\nNative USB stays on\nthe development board.\n\nBuilt-in Wi-Fi connects\nto the HTTPS backend.',163,116,1.15)
for ref,(name,x,y,w,t,b,pins,side) in MODS.items():main.place(ref,x,y,libname=name)
for ref,title,x,y in [('J2','MAX30102 / 0x57',25,33),('J3','MLX90614 / 0x5A',25,85),('J4','DS1302 RTC',25,121),('J7','EXTERNAL RGB LED',25,176),('J5','ST7789 TFT / 240 x 280',322,34),('J6','SPI MICROSD MODULE',322,106),('J8','BUZZER + DRIVER',250,169)]:main.text(title,x,y,1.4,True)
main.text('INT / unused',51,78,1.0)
# Explicit I2C branch wires: both sensors go to the same two controller pins.
for up,jpin,branch_x,y in [('4','3',105,70),('5','4',115,75)]:
    main.wire(main.p('U1',up),main.p('J2',jpin));main.dot((branch_x,y))
    p=main.p('J3',jpin);main.pathwire((branch_x,y),(branch_x,p[1]),p)
for up,jpin in [('6','3'),('7','4'),('14','5')]:main.wire(main.p('U1',up),main.p('J4',jpin))
for up,jpin in [('8','5'),('9','6'),('10','7'),('11','4'),('12','3')]:main.wire(main.p('U1',up),main.p('J5',jpin))
for up,jpin in [('21','6'),('40','3'),('41','4'),('42','5')]:main.wire(main.p('U1',up),main.p('J6',jpin))
# Shared cross-sheet names tie the explicit wires to the real carrier harness.
for n in U1NET:
    p=main.p('U1',n)
    if n in('3V3','GND'):main.netstub('U1',n,delta=(0,-7.62) if n=='3V3' else (0,7.62),angle=90 if n=='3V3' else 270)
    elif n in('4','5','6','7','14','16','17','18'):
        main.label(U1NET[n],(p[0]-15.24,p[1]),180)
    else:
        main.label(U1NET[n],(p[0]+(7.62 if n=='15' else 27.94),p[1]),0)
for ref in('J2','J3','J4'):
    main.netstub(ref,1);main.netstub(ref,2)
main.netstub('J7',4)
for ref,n in [('J5',1),('J5',2),('J5',8),('J6',1),('J6',2)]:main.netstub(ref,n,delta=(-7.62,0),angle=180)
# RGB drive, visible series resistors between the actual GPIO and each LED lead.
for r,up,jp,y in [('R3','16','1',195),('R4','17','2',200),('R5','18','3',205)]:
    main.place(r,110,y,270,showval=True)
    main.wire(main.p('U1',up),main.p(r,1));main.wire(main.p(r,2),main.p('J7',jp))
    main.label(CM[r]['pins']['2'],(main.p('J7',jp)[0]+12.7,main.p('J7',jp)[1]),180)
main.text('330 ohms per colour; common cathode to GND.',25,226,1)
# Actual NPN buzzer driver, including base pulldown and diode polarity.
main.place('R6',260,200,90,showval=True);main.place('Q1',295,200);main.place('R7',280,215,showval=True);main.place('D1',320,177.5,270)
main.wire(main.p('U1','15'),main.p('R6',1));main.pathwire(main.p('R6',2),(280,200),main.p('Q1',2));main.dot((280,200))
main.wire((280,200),main.p('R7',1))
main.wire((280,200),(280,191.77));main.label('BUZZ_BASE',(280,191.77),180)
main.pathwire(main.p('Q1',3),(main.p('Q1',3)[0],185),main.p('J8',2));main.dot((320,185))
main.pathwire(main.p('D1',2),(320,185));main.label('BUZZ_SW',main.p('J8',2),180)
main.pathwire(main.p('D1',1),(320,175),main.p('J8',1));main.dot((320,175));main.label('BUZZ_VCC',(320,175),180)
main.pathwire(main.p('Q1',1),(main.p('Q1',1)[0],225),(280,225),main.p('R7',2));main.label('GND',(280,225),0)
main.text('Q1 PN2222A: E1 / B2 / C3\nD1 1N5819: stripe/cathode toward buzzer +\nActive-high driver; buzzer 20 mA maximum.',250,231,1)
main.text('Selected V3V3 powers the modules; it is chosen on sheet 2. DEV3V3 is the controller output, not a short to external 3V3.',15,271,1)
main.text('Default screen is the working ST7789 TFT. A different OLED needs its own verified interface. GPIO40-42 must be available on the actual board.',15,277,1)
main.add(f'(sheet (at 20 245) (size 100 18) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {SID}) (property "Sheetname" "Power and carrier harness" (at 20 244 0) {eff(1.27,"left bottom")}) (property "Sheetfile" "NeoGuard-power.kicad_sch" (at 20 264 0) {eff(1.0,"left top")}) (instances (project "NeoGuard" (path "/{RID}" (page "2")))))')

power=Page('power','/'+RID+'/'+SID)
power.text('NEOGUARD | POWER AND CARRIER HARNESS',15,14,2.3,True)
power.text('This sheet preserves the real carrier connector pin numbers and the selectable supply topology.',15,22,1.15)
power.text('J1 / CONTROLLER CABLE',20,36,1.5,True);power.place('J1',75,66,autolabel=True)
power.text('J1 is a cable connector, not a devboard socket.\nMap each pin to the GPIO label on U1 / sheet 1.\nPin 2 is DEV3V3 from the ESP32 board.\nPins 1 and 21-24 are common ground returns.',20,108,1.1)
power.text('INPUT SUPPLIES',170,36,1.5,True);power.place('J9',205,55,autolabel=True)
power.text('J9 accepts already regulated supplies:\n1 = external 3V3; 2 = GND; 3 = external 5V.\nNo onboard regulator or reverse-polarity protection.',165,81,1.1)
power.text('JP1 / CARRIER 3V3 SOURCE',285,36,1.5,True);power.place('JP1',330,55,autolabel=True)
power.text('One shunt only:\n1-2 = DEV3V3 -> selected V3V3\n2-3 = EXT3V3 -> selected V3V3\nNever fit both positions.',285,81,1.1)
power.text('JP2 / SD MODULE SUPPLY',20,137,1.4,True);power.place('JP2',65,155,autolabel=True)
power.text('1-2 = V3V3; 2-3 = EXT5V.\nOne shunt only. Match the actual\nSD breakout supply rating.',20,179,1.05)
power.text('JP3 / BUZZER SUPPLY',155,137,1.4,True);power.place('JP3',200,155,autolabel=True)
power.text('1-2 = V3V3; 2-3 = EXT5V.\nOne shunt only. Match the buzzer\nrating; this driver is for <=20 mA.',155,179,1.05)
power.text('JP4 / TFT BACKLIGHT',285,137,1.4,True);power.place('JP4',330,155,autolabel=True)
power.text('Default OPEN / DNP.\nConnect only for a verified 3V3-compatible\nBL input with suitable driver/current limiting.',285,179,1.05)
power.text('DECOUPLING / BULK STORAGE',20,207,1.4,True)
for ref,x in [('C1',40),('C2',80),('C3',120),('C4',160)]:power.place(ref,x,230,showval=True,autolabel=True)
power.text('OPTIONAL I2C PULL-UPS',245,207,1.4,True)
power.place('R1',275,230,showval=True,autolabel=True);power.place('R2',350,230,showval=True,autolabel=True)
power.text('R1/R2 are DNP if module pull-ups already exist.\nI2C pull-ups go to selected V3V3, never 5V.',245,254,1.05)
power.text('Both copper layers use GND pours with thermals and stitching vias. Keep controller and modules powered together; signal isolation is not provided.',15,271,1)
power.text('All carrier interfaces use 3.3V logic. Confirm breakout voltages, physical connector order, purchased-part pinouts and current budget before fabrication.',15,277,1)

main.save('NeoGuard.kicad_sch','NeoGuard - ESP32-S3 System Connections',RID,1)
power.save('NeoGuard-power.kicad_sch','NeoGuard - Power and Carrier Harness',CID,2)
(ROOT/'NeoGuard.kicad_sym').write_text('(kicad_symbol_lib (version 20251024) (generator "neoguard_design")\n'+'\n'.join(dump(s) for s in LIBS.values())+'\n)\n',encoding='utf-8')
(ROOT/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "NeoGuard") (type "KiCad") (uri "${KIPRJMOD}/NeoGuard.kicad_sym") (options "") (descr "NeoGuard carrier and logical offboard controller")))\n')
(ROOT/'schematic_ids.json').write_text(json.dumps({'root_uuid':RID,'child_sheet_uuid':SID,'symbols':PLACED,'paths':PATHS,'logical_controller':{'reference':'U1','on_board':False,'pin_nets':U1NET}},indent=2))
print('Revision B schematic written: 26 carrier parts + offboard U1, two sheets, 119 pins including 1 NC.')
