import json
import re

def main():
    with open('SCH_IDLine_2026-09-21.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    shapes = data['schematics'][0]['dataStr']['shape']
    
    components = []
    wires = []
    net_labels = []
    
    for s in shapes:
        if s.startswith('LIB~'):
            parts = s.split('#@$')
            lib_head = parts[0]
            
            attr_part = lib_head.split('~')[3]
            attrs_raw = attr_part.split(chr(96))
            attrs = {}
            for i in range(0, len(attrs_raw)-1, 2):
                attrs[attrs_raw[i]] = attrs_raw[i+1]
                
            designator = 'Unknown'
            value = 'Unknown'
            pins = []
            
            for p in parts[1:]:
                p_parts = p.split('~')
                if p_parts[0] == 'T' and len(p_parts) > 13:
                    if p_parts[1] == 'P':
                        designator = p_parts[12]
                    elif p_parts[1] == 'N':
                        value = p_parts[12]
                elif p_parts[0] == 'P':
                    pin_id = p_parts[3] if len(p_parts) > 3 else '?'
                    pin_name_match = re.search(r'~([^~]+)~(?:end|start)', p)
                    pin_name = pin_name_match.group(1) if pin_name_match else '?'
                    try:
                        # Find the ^^ block that contains coords
                        # It looks like ^^x~y^^
                        coord_match = re.search(r'\^\^([-\d.]+)~([-\d.]+)\^\^', p)
                        if coord_match:
                            pin_x, pin_y = coord_match.groups()
                        else:
                            pin_x, pin_y = '0', '0'
                    except:
                        pin_x, pin_y = '0', '0'
                    
                    pins.append({
                        'id': pin_id,
                        'name': pin_name,
                        'x': float(pin_x),
                        'y': float(pin_y)
                    })
            
            package = attrs.get('package', 'None')
            components.append({
                'designator': designator,
                'value': value,
                'package': package,
                'pins': pins
            })
            
        elif s.startswith('W~'):
            # W~60 -695 45 -695 45 -680~...
            w_parts = s.split('~')
            pts_str = w_parts[1].split(' ')
            pts = []
            for i in range(0, len(pts_str), 2):
                pts.append((float(pts_str[i]), float(pts_str[i+1])))
            wires.append(pts)
            
        elif s.startswith('F~'):
            # F~part_netLabel...^^25~-685^^GND~...
            try:
                coord_match = re.search(r'\^\^([-\d.]+)~([-\d.]+)\^\^([^~]+)~', s)
                if coord_match:
                    x, y, name = coord_match.groups()
                    net_labels.append({'name': name, 'x': float(x), 'y': float(y)})
            except:
                pass
                
        elif s.startswith('J~'):
            # J~x~y...
            j_parts = s.split('~')
            # Treat junctions as points that wires can connect to, but wires usually overlap at junctions anyway
            pass

    # Build netlist from coords
    import collections
    adj = collections.defaultdict(set)

    for pts in wires:
        for i in range(len(pts) - 1):
            p1 = (pts[i][0], pts[i][1])
            p2 = (pts[i+1][0], pts[i+1][1])
            adj[p1].add(p2)
            adj[p2].add(p1)

    # Pin locations
    pin_to_comp = {}
    all_pins = []
    for c in components:
        for p in c['pins']:
            coord = (p['x'], p['y'])
            pin_info = {'ref': c['designator'], 'pin': p['name'], 'id': p['id'], 'coord': coord}
            all_pins.append(pin_info)
            if coord not in pin_to_comp:
                pin_to_comp[coord] = []
            pin_to_comp[coord].append(pin_info)

    # Map labels
    net_names = {}
    for nl in net_labels:
        coord = (nl['x'], nl['y'])
        net_names[coord] = nl['name']

    # Connected components
    visited = set()
    conn_comps = []
    
    # ensure all pin coords are in adj
    for pin in all_pins:
        if pin['coord'] not in adj:
            adj[pin['coord']] = set()
            
    # ensure all net label coords are in adj
    for nl in net_labels:
        coord = (nl['x'], nl['y'])
        if coord not in adj:
            adj[coord] = set()

    for node in adj.keys():
        if node not in visited:
            comp = set()
            stack = [node]
            while stack:
                curr = stack.pop()
                if curr not in visited:
                    visited.add(curr)
                    comp.add(curr)
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            stack.append(neighbor)
            conn_comps.append(comp)

    # Analyze nets
    output_report = []

    output_report.append("### 1. Component List")
    for c in components:
        output_report.append(f"- **{c['designator']}**: {c['value']} ({c['package']})")

    output_report.append("\n### 2. Nets List")
    nets_data = []
    unnamed_nets = []
    unconnected_pins = []
    net_counter = 1

    for comp in conn_comps:
        comp_pins = []
        comp_names = set()
        for node in comp:
            if node in pin_to_comp:
                comp_pins.extend(pin_to_comp[node])
            if node in net_names:
                comp_names.add(net_names[node])
        
        if len(comp_pins) == 1 and not comp_names:
            unconnected_pins.append(comp_pins[0])
            continue
            
        if len(comp_pins) == 0:
            continue
            
        net_name = ' / '.join(list(comp_names))
        if not net_name:
            net_name = f"Unnamed_Net_{net_counter}"
            net_counter += 1
            unnamed_nets.append({'name': net_name, 'pins': comp_pins})
            
        nets_data.append({'name': net_name, 'pins': comp_pins})

    for n in nets_data:
        pin_strs = [f"{p['ref']}.{p['pin']}" for p in n['pins']]
        output_report.append(f"- **{n['name']}**: {', '.join(pin_strs)}")

    output_report.append("\n### 3. Integrity Verification")

    output_report.append("\n**Unnamed/Floating Nets:**")
    if unnamed_nets:
        for n in unnamed_nets:
            pin_strs = [f"{p['ref']}.{p['pin']}" for p in n['pins']]
            output_report.append(f"- {n['name']} connecting: {', '.join(pin_strs)}")
    else:
        output_report.append("- None")

    output_report.append("\n**Unconnected Pins:**")
    if unconnected_pins:
        for p in unconnected_pins:
            output_report.append(f"- {p['ref']}.{p['pin']}")
    else:
        output_report.append("- None")
        
    output_report.append("\n**Duplicate Components:**")
    designators = [c['designator'] for c in components]
    dups = [item for item, count in collections.Counter(designators).items() if count > 1]
    if dups:
        output_report.append(f"- Duplicates found: {', '.join(dups)}")
    else:
        output_report.append("- None")

    with open('report2.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_report))

if __name__ == '__main__':
    main()
