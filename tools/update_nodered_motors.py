import urllib.request
import json

req = urllib.request.urlopen('http://127.0.0.1:1880/flows', timeout=2)
flows = json.loads(req.read().decode('utf-8'))

# 1. Update sliders to 'all' so they respond continuously
for n in flows:
    if n.get('id') in ['c9baf08a6eaf1a4c', '2c7919fbbb7ad85f']:
        n['outs'] = 'all'

# 2. Adjust Paro and Test button sizes in grp_motores
for n in flows:
    if n.get('id') == 'b8d5e1358cfabd20':
        n['order'] = 7
        n['width'] = 2
        n['label'] = 'PARO'
    if n.get('id') == '23767e58df4260b5':
        n['order'] = 8
        n['width'] = 2
        n['label'] = 'TEST'

# 3. Add directional buttons for natural driving
new_nodes = [
    {
        'id': 'btn_drive_left',
        'type': 'ui_button',
        'z': '4b6153b77b02556e',
        'name': 'Giro Izq',
        'group': 'grp_motores',
        'order': 3,
        'width': 2,
        'height': 1,
        'passthru': False,
        'label': 'GIRO IZQ',
        'color': '#FFFFFF',
        'bgcolor': '#1976D2',
        'icon': 'arrow_back',
        'payload': '{"cmd":"set_motores","m1":-150,"m2":150}',
        'payloadType': 'json',
        'topic': '',
        'x': 190,
        'y': 660,
        'wires': [['c28ae4ac241a7b5f']]
    },
    {
        'id': 'btn_drive_fwd',
        'type': 'ui_button',
        'z': '4b6153b77b02556e',
        'name': 'Adelante',
        'group': 'grp_motores',
        'order': 4,
        'width': 2,
        'height': 1,
        'passthru': False,
        'label': 'AVANZAR',
        'color': '#FFFFFF',
        'bgcolor': '#2E7D32',
        'icon': 'arrow_upward',
        'payload': '{"cmd":"set_motores","m1":180,"m2":180}',
        'payloadType': 'json',
        'topic': '',
        'x': 190,
        'y': 700,
        'wires': [['c28ae4ac241a7b5f']]
    },
    {
        'id': 'btn_drive_right',
        'type': 'ui_button',
        'z': '4b6153b77b02556e',
        'name': 'Giro Der',
        'group': 'grp_motores',
        'order': 5,
        'width': 2,
        'height': 1,
        'passthru': False,
        'label': 'GIRO DER',
        'color': '#FFFFFF',
        'bgcolor': '#1976D2',
        'icon': 'arrow_forward',
        'payload': '{"cmd":"set_motores","m1":150,"m2":-150}',
        'payloadType': 'json',
        'topic': '',
        'x': 190,
        'y': 740,
        'wires': [['c28ae4ac241a7b5f']]
    },
    {
        'id': 'btn_drive_rev',
        'type': 'ui_button',
        'z': '4b6153b77b02556e',
        'name': 'Atras',
        'group': 'grp_motores',
        'order': 6,
        'width': 2,
        'height': 1,
        'passthru': False,
        'label': 'REVERSA',
        'color': '#FFFFFF',
        'bgcolor': '#D32F2F',
        'icon': 'arrow_downward',
        'payload': '{"cmd":"set_motores","m1":-180,"m2":-180}',
        'payloadType': 'json',
        'topic': '',
        'x': 190,
        'y': 780,
        'wires': [['c28ae4ac241a7b5f']]
    }
]

existing_ids = {n.get('id') for n in flows}
for node in new_nodes:
    if node['id'] not in existing_ids:
        flows.append(node)

req2 = urllib.request.Request(
    'http://127.0.0.1:1880/flows',
    data=json.dumps(flows).encode('utf-8'),
    headers={'Content-Type': 'application/json', 'Node-RED-Deployment-Type': 'full'},
    method='POST'
)
res = urllib.request.urlopen(req2)
print('Node-RED flow actualizado con exito! Codigo:', res.status)
