import json
from typing import Dict, Any, List
from pcb_copilot.schemas import PCBDesignPlan
from pcb_copilot.config import FOOTPRINT_LIBRARY


class EasyEDAGenerator:
    """
    Transforms PCBDesignPlan into standard EasyEDA PCB JSON format.
    """

    def __init__(self, plan: PCBDesignPlan):
        self.plan = plan

    def generate_easyeda_json(self) -> Dict[str, Any]:
        """
        Builds complete EasyEDA PCB JSON dictionary.
        """
        bw = self.plan.board_width_mm
        bh = self.plan.board_height_mm

        easyeda_doc: Dict[str, Any] = {
            "head": {
                "docType": "3",  # 3 = PCB Design
                "editorVersion": "6.5.22",
                "title": self.plan.project_title,
                "c_para": {
                    "package": "",
                    "BBOX": f"0 0 {bw * 10} {bh * 10}"
                }
            },
            "canvas": {
                "width": f"{bw}mm",
                "height": f"{bh}mm",
                "gridSize": "2.54mm",
                "gridColor": "#222222",
                "backgroundColor": "#111827"
            },
            "shape": [],
            "BBOX": {
                "x": 0,
                "y": 0,
                "width": bw,
                "height": bh
            },
            "components": [],
            "layers": [
                {"id": 1, "name": "TopLayer", "color": "#FF0000", "visible": True},
                {"id": 2, "name": "BottomLayer", "color": "#0000FF", "visible": True},
                {"id": 3, "name": "TopSilkscreen", "color": "#F1C40F", "visible": True},
                {"id": 10, "name": "BoardOutline", "color": "#00FF00", "visible": True}
            ]
        }

        # 1. Add Board Outline shape (BoardOutline layer 10)
        easyeda_doc["shape"].append(
            f"TRACK~10~1~0~0 0 {bw} 0 {bw} {bh} 0 {bh} 0 0~gge1~0"
        )

        # 2. Add Component shapes & Pads
        for idx, comp in enumerate(self.plan.components):
            comp_id = f"gge{idx + 10}"
            easy_footprint = FOOTPRINT_LIBRARY.get(comp.name, {}).get("easyeda", comp.footprint)

            comp_entry = {
                "head": {
                    "type": "LIB",
                    "gId": comp_id,
                    "x": comp.x_mm * 10,  # EasyEDA uses 10 mil / pixel scaling internally
                    "y": comp.y_mm * 10,
                    "rotation": comp.rotation_deg,
                    "layerid": "1"
                },
                "item": {
                    "ref": comp.designator,
                    "name": comp.name,
                    "package": easy_footprint,
                    "value": comp.value or ""
                },
                "pads": []
            }

            for p_idx, pin in enumerate(comp.pins):
                pad_entry = {
                    "number": pin.pin_number,
                    "name": pin.pin_name,
                    "net": pin.net_name,
                    "x": (comp.x_mm + (p_idx * 2.54)) * 10,
                    "y": comp.y_mm * 10
                }
                comp_entry["pads"].append(pad_entry)

                # Add pad shape line to EasyEDA shapes string array
                easyeda_doc["shape"].append(
                    f"PAD~1~{pad_entry['x']}~{pad_entry['y']}~1.5~1.5~1~{comp_id}p{p_idx+1}~{pin.pin_number}~{pin.net_name}~0"
                )

            easyeda_doc["components"].append(comp_entry)

        # 3. Add Copper Tracks between pins
        track_idx = 100
        for comp in self.plan.components:
            for pin in comp.pins:
                if pin.net_name and pin.net_name != "GND":
                    # Add virtual track connection string
                    easyeda_doc["shape"].append(
                        f"TRACK~1~0.25~0~{comp.x_mm * 10} {comp.y_mm * 10} {(comp.x_mm + 5) * 10} {(comp.y_mm + 5) * 10}~gge{track_idx}~0"
                    )
                    track_idx += 1

        return easyeda_doc

    def generate_easyeda_json_string(self) -> str:
        """Returns pretty-printed JSON string."""
        return json.dumps(self.generate_easyeda_json(), indent=2)
