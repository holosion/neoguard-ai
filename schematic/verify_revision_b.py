"""Independent pin/net checks. Run with the Python supplied with KiCad 10."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import pcbnew as pcb

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'design_manifest.json').read_text())
xml = ET.parse(root / 'NeoGuard.net.xml')
nodes = {(n.attrib['ref'], n.attrib['pin']): net.attrib['name']
         for net in xml.findall('.//nets/net') for n in net.findall('node')}
clean = lambda value: value.lstrip('/') if value else value
expected_u1 = {
    '4': 'I2C_SDA_GPIO4', '5': 'I2C_SCL_GPIO5',
    '6': 'RTC_CLK_GPIO6', '7': 'RTC_DAT_GPIO7', '14': 'RTC_CE_GPIO14',
    '8': 'TFT_RST_GPIO8', '9': 'TFT_DC_GPIO9', '10': 'TFT_CS_GPIO10',
    '11': 'TFT_MOSI_GPIO11', '12': 'TFT_SCK_GPIO12',
    '21': 'SD_CS_GPIO21', '40': 'SD_SCK_GPIO40',
    '41': 'SD_MOSI_GPIO41', '42': 'SD_MISO_GPIO42',
    '15': 'BUZZ_GPIO15', '16': 'LED_R_GPIO16',
    '17': 'LED_G_GPIO17', '18': 'LED_B_GPIO18',
    '3V3': 'DEV3V3', 'GND': 'GND',
}
for part in manifest['components']:
    for pin, net in part['pins'].items():
        if net is not None:
            actual = clean(nodes.get((part['ref'], pin)))
            assert actual == net, ('schematic', part['ref'], pin, net, actual)
for pin, net in expected_u1.items():
    assert clean(nodes.get(('U1', pin))) == net, ('U1', pin, net, nodes.get(('U1', pin)))
u1 = next(c for c in xml.findall('.//components/comp') if c.get('ref') == 'U1')
u1_properties = {p.get('name'): p.get('value') for p in u1.findall('property')}
assert 'exclude_from_board' in u1_properties, u1_properties
assert clean(nodes[('U1', '3V3')]) != clean(nodes[('J2', '1')]), 'Power selector bypassed'

board = pcb.LoadBoard(str(root / 'NeoGuard.kicad_pcb'))
parts = {f.GetReference(): f for f in board.GetFootprints()}
assert 'U1' not in parts, 'Offboard controller incorrectly added to PCB'
pad_count = 0
for part in manifest['components']:
    assert part['ref'] in parts
    pads = {p.GetNumber(): p for p in parts[part['ref']].Pads()}
    for number, net in part['pins'].items():
        pad_count += 1
        assert number in pads
        actual = clean(pads[number].GetNetname())
        if net is None:
            assert not actual or actual.startswith('unconnected-'), (part['ref'], number, actual)
        else:
            assert actual == net, ('PCB', part['ref'], number, net, actual)
assert pad_count == 99
assert board.GetCopperLayerCount() == 2
zone_data = []
for zone in board.Zones():
    assert zone.GetNetname() == 'GND'
    assert zone.GetPadConnection() == pcb.ZONE_CONNECTION_THERMAL
    area = zone.GetFilledPolysList(zone.GetLayer()).Area() / 1e12
    assert area > 10000, ('Empty or unexpectedly fragmented ground zone', area)
    zone_data.append({'layer': board.GetLayerName(zone.GetLayer()), 'filled_area_mm2': round(area, 2)})
assert {z['layer'] for z in zone_data} == {'F.Cu', 'B.Cu'}
ground_vias = [t for t in board.GetTracks() if isinstance(t, pcb.PCB_VIA) and t.GetNetname() == 'GND']
assert len(ground_vias) >= 20
erc = json.loads((root / 'ERC.json').read_text())
drc = json.loads((root / 'pcb_drc.json').read_text())
assert not any(s.get('violations') for s in erc['sheets'])
assert not drc['violations'] and not drc['unconnected_items'] and not drc['schematic_parity']
result = {'revision': 'B', 'carrier_pad_checks': pad_count, 'controller_pin_checks': len(expected_u1),
          'carrier_net_mismatches': 0, 'controller_net_mismatches': 0,
          'copper_layers': board.GetCopperLayerCount(), 'ground_vias': len(ground_vias),
          'ground_zones': zone_data, 'erc_violations': 0, 'drc_violations': 0,
          'unconnected_items': 0, 'schematic_parity_issues': 0}
(root / 'verification_summary.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
