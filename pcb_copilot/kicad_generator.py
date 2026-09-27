import uuid
import math
from typing import Dict, List, Tuple
from pcb_copilot.schemas import PCBDesignPlan, Component
from pcb_copilot.config import FOOTPRINT_LIBRARY, EDGE_MARGIN_MM, GRID_SIZE_MM


def apply_auto_placement(plan: PCBDesignPlan) -> PCBDesignPlan:
    """
    Intelligent cluster & grid auto-placement algorithm.
    Positions components optimally within board boundaries.
    """
    bw = plan.board_width_mm
    bh = plan.board_height_mm

    # Categorize components
    mcus = [c for c in plan.components if "esp32" in c.name.lower() or "mcu" in c.name.lower()]
    power_components = [c for c in plan.components if "ldo" in c.name.lower() or "ams1117" in c.name.lower() or "header" in c.name.lower() or c.designator == "J1"]
    rf_modules = [c for c in plan.components if "lora" in c.name.lower() or "ra-02" in c.name.lower()]
    gps_modules = [c for c in plan.components if "gps" in c.name.lower() or "neo-6m" in c.name.lower()]
    passives = [c for c in plan.components if c not in mcus and c not in power_components and c not in rf_modules and c not in gps_modules]

    placed = set()

    # 1. Place Main MCU near center
    if mcus:
        mcu = mcus[0]
        mcu.x_mm = round(bw * 0.45, 2)
        mcu.y_mm = round(bh * 0.50, 2)
        mcu.rotation_deg = 0.0
        placed.add(mcu.designator)

    # 2. Place Power LDO & Connector on left side
    x_pwr = round(EDGE_MARGIN_MM + 8.0, 2)
    y_pwr = round(EDGE_MARGIN_MM + 8.0, 2)
    for p in power_components:
        if p.designator not in placed:
            p.x_mm = x_pwr
            p.y_mm = y_pwr
            y_pwr += 15.0
            placed.add(p.designator)

    # 3. Place RF Module top-right (antenna keepout zone)
    if rf_modules:
        rf = rf_modules[0]
        rf.x_mm = round(bw - EDGE_MARGIN_MM - 12.0, 2)
        rf.y_mm = round(EDGE_MARGIN_MM + 12.0, 2)
        placed.add(rf.designator)

    # 4. Place GPS Module bottom-right
    if gps_modules:
        gps = gps_modules[0]
        gps.x_mm = round(bw - EDGE_MARGIN_MM - 12.0, 2)
        gps.y_mm = round(bh - EDGE_MARGIN_MM - 10.0, 2)
        placed.add(gps.designator)

    # 5. Place Passives (Resistors & Capacitors) clustered near MCU/Power
    cur_x = 22.0
    cur_y = bh - 10.0
    for p in passives:
        if p.designator not in placed:
            p.x_mm = round(cur_x, 2)
            p.y_mm = round(cur_y, 2)
            cur_x += 8.0
            if cur_x > (bw - 15.0):
                cur_x = 22.0
                cur_y -= 8.0
            placed.add(p.designator)

    return plan


class KiCadGenerator:
    """
    Native KiCad 6 / 7 / 8 PCB S-Expression (.kicad_pcb) & Schematic (.kicad_sch) exporter.
    """

    def __init__(self, plan: PCBDesignPlan):
        self.plan = apply_auto_placement(plan)
        self.net_map: Dict[str, int] = {"": 0}
        self._build_net_map()

    def _build_net_map(self):
        """Map all unique net names to integer IDs."""
        net_id = 1
        for comp in self.plan.components:
            for pin in comp.pins:
                if pin.net_name and pin.net_name not in self.net_map:
                    self.net_map[pin.net_name] = net_id
                    net_id += 1

    def generate_kicad_pcb(self) -> str:
        """
        Generates valid KiCad S-Expression PCB layout text (.kicad_pcb format).
        """
        bw = self.plan.board_width_mm
        bh = self.plan.board_height_mm

        lines = []
        lines.append('(kicad_pcb (version 20211014) (generator pcb_copilot)')
        lines.append('  (general')
        lines.append('    (thickness 1.6)')
        lines.append('  )')
        lines.append('  (paper "A4")')
        lines.append('  (layers')
        lines.append('    (0 "F.Cu" signal)')
        lines.append('    (31 "B.Cu" signal)')
        lines.append('    (32 "B.Adhes" user "B.Adhesive")')
        lines.append('    (33 "F.Adhes" user "F.Adhesive")')
        lines.append('    (34 "B.Paste" user)')
        lines.append('    (35 "F.Paste" user)')
        lines.append('    (36 "B.SilkS" user "B.Silkscreen")')
        lines.append('    (37 "F.SilkS" user "F.Silkscreen")')
        lines.append('    (38 "B.Mask" user)')
        lines.append('    (39 "F.Mask" user)')
        lines.append('    (44 "Edge.Cuts" user)')
        lines.append('  )')
        lines.append('')
        lines.append('  (setup')
        lines.append('    (pad_to_mask_clearance 0.05)')
        lines.append('    (pcbplotparams')
        lines.append('      (layerselection 0x00010fc_00000001)')
        lines.append('      (usegerberextensions true)')
        lines.append('    )')
        lines.append('  )')
        lines.append('')

        # Add Net definitions
        for net_name, net_id in self.net_map.items():
            lines.append(f'  (net {net_id} "{net_name}")')

        lines.append('')

        # Add PCB Outline Graphics (Edge.Cuts)
        lines.append(f'  (gr_line (start 0 0) (end {bw} 0) (layer "Edge.Cuts") (width 0.15))')
        lines.append(f'  (gr_line (start {bw} 0) (end {bw} {bh}) (layer "Edge.Cuts") (width 0.15))')
        lines.append(f'  (gr_line (start {bw} {bh}) (end 0 {bh}) (layer "Edge.Cuts") (width 0.15))')
        lines.append(f'  (gr_line (start 0 {bh}) (end 0 0) (layer "Edge.Cuts") (width 0.15))')
        lines.append('')

        # Add Footprints
        for comp in self.plan.components:
            fp_lines = self._generate_footprint_sexpr(comp)
            lines.extend(fp_lines)

        lines.append('')

        # Add Connection Routing Tracks / Ratsnest segments
        track_lines = self._generate_routing_tracks()
        lines.extend(track_lines)

        lines.append(')')
        return "\n".join(lines)

    def _generate_footprint_sexpr(self, comp: Component) -> List[str]:
        """Generates S-expression block for a single component footprint."""
        lines = []
        fp_name = comp.footprint or "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
        comp_uuid = str(uuid.uuid4())

        lines.append(f'  (footprint "{fp_name}" (at {comp.x_mm} {comp.y_mm} {comp.rotation_deg}) (layer "{comp.layer}")')
        lines.append(f'    (tedit 61000000) (uuid "{comp_uuid}")')
        lines.append(f'    (property "Reference" "{comp.designator}" (at 0 -2.5 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))')
        lines.append(f'    (property "Value" "{comp.value or comp.name}" (at 0 2.5 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')

        # Compute pin pad positions around component center
        num_pins = len(comp.pins)
        for idx, pin in enumerate(comp.pins):
            net_id = self.net_map.get(pin.net_name, 0)

            # Simple dual-in-line / perimeter pad offset math
            if num_pins <= 4:
                offset_x = (idx - (num_pins - 1) / 2.0) * 2.54
                offset_y = -1.5 if idx % 2 == 0 else 1.5
            else:
                half = num_pins // 2
                if idx < half:
                    offset_x = -4.0
                    offset_y = (idx - half / 2.0) * 2.0
                else:
                    offset_x = 4.0
                    offset_y = ((idx - half) - half / 2.0) * 2.0

            lines.append(
                f'    (pad "{pin.pin_number}" smd rect (at {offset_x:.2f} {offset_y:.2f}) '
                f'(size 1.2 1.2) (layers "F.Cu" "F.Mask") '
                f'(net {net_id} "{pin.net_name}"))'
            )

        lines.append('  )')
        return lines

    def _generate_routing_tracks(self) -> List[str]:
        """Generate connecting copper track segments between matching nets."""
        lines = []

        # Collect pin coordinates per net
        net_pads: Dict[str, List[Tuple[float, float]]] = {}

        for comp in self.plan.components:
            num_pins = len(comp.pins)
            for idx, pin in enumerate(comp.pins):
                if not pin.net_name or pin.net_name == "GND":
                    continue  # GND handled by ground plane

                if num_pins <= 4:
                    offset_x = (idx - (num_pins - 1) / 2.0) * 2.54
                    offset_y = -1.5 if idx % 2 == 0 else 1.5
                else:
                    half = num_pins // 2
                    if idx < half:
                        offset_x = -4.0
                        offset_y = (idx - half / 2.0) * 2.0
                    else:
                        offset_x = 4.0
                        offset_y = ((idx - half) - half / 2.0) * 2.0

                pad_x = comp.x_mm + offset_x
                pad_y = comp.y_mm + offset_y

                if pin.net_name not in net_pads:
                    net_pads[pin.net_name] = []
                net_pads[pin.net_name].append((pad_x, pad_y))

        # Generate segments connecting pads in each net
        for net_name, coords in net_pads.items():
            if len(coords) > 1:
                net_id = self.net_map.get(net_name, 0)
                width = 0.5 if net_name in ["+3V3", "+5V"] else 0.25
                for i in range(len(coords) - 1):
                    x1, y1 = coords[i]
                    x2, y2 = coords[i + 1]
                    lines.append(
                        f'  (segment (start {x1:.2f} {y1:.2f}) (end {x2:.2f} {y2:.2f}) '
                        f'(width {width}) (layer "F.Cu") (net {net_id}))'
                    )
        return lines

    def generate_kicad_sch(self) -> str:
        """Generates KiCad Schematic file string (.kicad_sch)."""
        lines = [
            '(kicad_sch (version 20211123) (generator pcb_copilot)',
            '  (uuid "d0a85e68-0000-4000-8000-000000000000")',
            '  (paper "A4")',
            '  (title_block',
            f'    (title "{self.plan.project_title}")',
            '    (company "PCB-Copilot AI")',
            '  )'
        ]
        for comp in self.plan.components:
            lines.append(f'  (symbol (lib_id "{comp.name}") (at {comp.x_mm * 2} {comp.y_mm * 2} 0)')
            lines.append(f'    (property "Reference" "{comp.designator}" (at 0 -5 0))')
            lines.append(f'    (property "Value" "{comp.value or comp.name}" (at 0 5 0))')
            lines.append('  )')
        lines.append(')')
        return "\n".join(lines)
