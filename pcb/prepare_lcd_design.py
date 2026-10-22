"""Create the LCD revision without modifying the earlier TFT project."""
from pathlib import Path
import json, shutil, re

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'schematic'
m = json.loads((OLD/'design_manifest.json').read_text())
m.update(revision='LCD-C', date='2026-10-22', design_type='LCD module carrier; controller on functional cable header; mechanical fit unconfirmed')
rename = dict(zip(['TFT_RST_GPIO8','TFT_DC_GPIO9','TFT_CS_GPIO10','TFT_MOSI_GPIO11','TFT_SCK_GPIO12'], ['LCD_RS_GPIO8','LCD_EN_GPIO9','LCD_D4_GPIO10','LCD_D5_GPIO11','LCD_D6_GPIO12']))
m['components'] = [c for c in m['components'] if c['ref'] != 'JP4']
for c in m['components']:
    c['pins'] = {k:rename.get(v,v) for k,v in c['pins'].items()}
cm = {c['ref']:c for c in m['components']}
cm['J1']['pins']['22'] = 'LCD_D7_GPIO13'
cm['J5'].update(value='WC1602A LCD 16x2 - VERIFY ACTUAL MODULE', symbol='Display_Character:WC1602A', footprint='Display:WC1602A', pins={str(i):n for i,n in enumerate(['GND','EXT5V','LCD_CONTRAST','LCD_RS_5V','GND','LCD_EN_5V',None,None,None,None,'LCD_D4_5V','LCD_D5_5V','LCD_D6_5V','LCD_D7_5V','LCD_LED_A','GND'],1)})
def add(ref,value,symbol,footprint,pins):
    c=dict(ref=ref,value=value,symbol=symbol,footprint=footprint,pins={str(k):v for k,v in pins.items()});m['components'].append(c)
add('U2','SN74AHCT245N - NOT 74HC245','74xx:74HC245','Package_DIP:DIP-20_W7.62mm', {1:'EXT5V',2:'LCD_RS_GPIO8',3:'LCD_EN_GPIO9',4:'LCD_D4_GPIO10',5:'LCD_D5_GPIO11',6:'LCD_D6_GPIO12',7:'LCD_D7_GPIO13',8:'GND',9:'GND',10:'GND',11:None,12:None,13:'LCD_D7_5V',14:'LCD_D6_5V',15:'LCD_D5_5V',16:'LCD_D4_5V',17:'LCD_EN_5V',18:'LCD_RS_5V',19:'GND',20:'EXT5V'})
add('RV1','10k LCD CONTRAST','Device:R_Potentiometer','Potentiometer_THT:Potentiometer_Bourns_3296W_Vertical',{1:'EXT5V',2:'LCD_CONTRAST',3:'GND'})
add('R8','220 LCD BACKLIGHT','Device:R',cm['R3']['footprint'],{1:'EXT5V',2:'LCD_LED_A'})
add('C5','100nF U2 BYPASS','Device:C',cm['C1']['footprint'],{1:'EXT5V',2:'GND'})
add('C6','10uF 10V LCD','Device:C_Polarized',cm['C2']['footprint'],{1:'EXT5V',2:'GND'})
(ROOT/'design_manifest.json').write_text(json.dumps(m,indent=2))
shutil.copy2(OLD/'NeoGuard.kicad_pro', ROOT/'NeoGuard.kicad_pro')
shutil.copy2(OLD/'fp-lib-table', ROOT/'fp-lib-table')

# Retain the proven KiCad symbol parser and schematic writer, not old connectivity.
src=(OLD/'build_schematic_rev_b.py').read_text()
prefix=src[:src.index('# Absolute page coordinates')]
helpers=src[src.index('def pin_defs('):src.index("main=Page('main'")]
helpers=helpers.replace('2026-10-21','2026-10-22').replace('(rev "B")','(rev "LCD-C")')
helpers=helpers.replace("if ref=='U1':ry=43;vy=37", "if ref=='U1':ry=y-65;vy=y-70")
helpers=helpers.replace("ref!='U1'", "ref!='U1'")
helpers=helpers.replace('if ref=="U1" else', 'if ref=="U1" or ref.startswith("#") else')
controller='''
# Fixed-direction symbol for the hardwired A->B buffer; no bidirectional outputs on A.
buffer=LIBS.pop('74HC245')
rename(buffer,'74HC245','SN74AHCT245_AtoB');buffer[1]='SN74AHCT245_AtoB'
for sub in children(buffer,'symbol'):
 for pin in children(sub,'pin'):
  number=int(child(pin,'number')[1])
  if 2 <= number <= 9: pin[1]=Atom('input')
  elif 11 <= number <= 18: pin[1]=Atom('output')
LIBS['SN74AHCT245_AtoB']=buffer
CM['U2']['symbol']='NeoGuard:SN74AHCT245_AtoB'
U1NET = {'4':'I2C_SDA_GPIO4','5':'I2C_SCL_GPIO5','6':'RTC_CLK_GPIO6','7':'RTC_DAT_GPIO7','14':'RTC_CE_GPIO14','8':'LCD_RS_GPIO8','9':'LCD_EN_GPIO9','10':'LCD_D4_GPIO10','11':'LCD_D5_GPIO11','12':'LCD_D6_GPIO12','13':'LCD_D7_GPIO13','15':'BUZZ_GPIO15','16':'LED_R_GPIO16','17':'LED_G_GPIO17','18':'LED_B_GPIO18','21':'SD_CS_GPIO21','40':'SD_SCK_GPIO40','41':'SD_MOSI_GPIO41','42':'SD_MISO_GPIO42','3V3':'DEV3V3','GND':'GND'}
custom_module('ESP32_S3_Logical',45,60,-60,[(n,net.replace('_GPIO',' / GPIO'),55.88-i*5.08) for i,(n,net) in enumerate(U1NET.items())])
'''
(ROOT/'build_schematic.py').write_text(prefix+controller+helpers+(ROOT/'schematic_pages.py.txt').read_text())

# Place the module and its real 3D model, then route once using the existing router.
base=(OLD/'build_pcb.py').read_text()
base=base[base.index('import json'):base.index('# Compact labels')]
a=base.index("if __name__=='__main__'");b=base.index('M = json.loads',a)
base=base[:a]+base[b:]
base=base.replace("'J2':(64.008,34.036,90)","'J2':(55.118,34.036,90)")
base=base.replace("'J3':(83.058,34.036,90)","'J3':(55.118,44.196,90)")
base=base.replace("'J4':(107.95,34.036,90)","'J4':(55.118,54.356,90)")
base=base.replace("'R1':(58.928,49.022,0)","'R1':(54.102,39.116,0)")
base=base.replace("'R2':(58.928,57.15,0)","'R2':(54.102,49.276,0)")
base=base.replace("'J5':(149.098,45.974,0)","'J5':(80.01,28.956,0)")
base=base.replace("'J6':(149.098,84.074,0)","'J6':(149.098,96.012,0)")
base=base.replace("'JP2':(132.08,91.948,0)","'JP2':(132.08,104.14,90)")
base=base.replace("'C1':(67.056,40.132,0)","'C1':(54.102,64.008,0)")
base=base.replace("'C2':(55.118,40.132,0)","'C2':(64.008,64.008,0)")
base=base.replace("'C3':(125.984,77.978,0)","'C3':(131.064,91.948,0)")
base=base.replace("'C4':(140.208,77.978,0)","'C4':(141.224,91.948,0), 'U2':(114.046,68.072,0), 'RV1':(140.208,69.088,0), 'R8':(133.096,81.026,0), 'C5':(126.492,67.056,0), 'C6':(104.14,69.088,0)")
base=base.replace('(155,25)','(156,24)')
base=base.replace("'ST7789 TFT'","'16x2 LCD ON BOARD'")
base=base.replace("'NEOGUARD  |  MODULE CARRIER  |  REV A'","'AKENA NEOGUARD  |  LCD CARRIER  |  REV C'")
base=base.replace("'FUNCTIONAL CABLE HEADERS - VERIFY MODULE PIN ORDER'","'REVIEW PROTOTYPE - VERIFY LCD / MODULE DIMENSIONS'")
base=base.replace("'3.3V LOGIC ONLY   |   NO ONBOARD REGULATOR'","'3V3 SENSORS  |  5V LCD VIA AHCT245  |  REGULATED INPUTS'")
base=base.replace("'ONE SHUNT ONLY ON EACH 3-PIN SELECTOR'","'ONE SHUNT PER SELECTOR - DO NOT BRIDGE USB AND EXT POWER'")
base=base.replace('max(.8,size)','max(.8,size)')
base+= '''
# Four dedicated LCD mounting holes. Their positions are an explicit WC1602A assumption.
for hole in byref['J5'].Pads():
 if not hole.GetNumber():
  hole.SetAttribute(p.PAD_ATTRIB_NPTH)
  hole.SetShape(p.PAD_SHAPE_CIRCLE);hole.SetSize(v(2.7,2.7));hole.SetDrillSize(v(2.7,2.7))
for fp in board.GetFootprints():
 fp.Reference().SetVisible(False)
for ref,label in {'J1':'ESP32-S3 CABLE','J2':'MAX30102','J3':'MLX90614','J4':'DS1302','J6':'SD CARD','J7':'RGB R G B GND','J8':'BUZZER + -','J9':'EXT 3V3 GND 5V','JP1':'3V3 SOURCE','JP2':'SD SUPPLY','JP3':'BUZZ SUPPLY','U2':'AHCT245 5V','RV1':'LCD CONTRAST','R8':'LCD LED 220R'}.items():
 x,y,r=POS[ref];text(ref+' '+label,x-2,y-4,0.85)
text('LCD1602: RS8 EN9 D4:10 D5:11 D6:12 D7:13',111,66,0.8)
text('LCD MOUNTING: WC1602A 80 x 36 mm ASSUMED',111,60,.8)
text('J1 IS A CABLE HEADER, NOT A DEVBOARD SOCKET',53,88,.8)
text('I2C SDA4 / SCL5',60,27,.85)
p.SaveBoard(str(ROOT/'NeoGuard.kicad_pcb'),board)
from route_lcd import run
run()
'''
(ROOT/'build_pcb.py').write_text(base)
route=(OLD/'refine_pcb_revision_b.py').read_text()
route=route.replace("'BUZZ_SW'}","'BUZZ_SW','LCD_LED_A'}")
route=route.replace('apply_paths(board);finish_silk_and_outline(board)','apply_paths(board)')
route=route.replace("SetRevision('B')","SetRevision('LCD-C')").replace('2026-10-21','2026-10-22')
route=route.replace('NeoGuard module carrier - thermal ground pours and 45-degree routing','Akena NeoGuard LCD carrier - mechanical assumptions unconfirmed')
(ROOT/'route_lcd.py').write_text(route)
print('Prepared LCD manifest, schematic generator and PCB builder.')
