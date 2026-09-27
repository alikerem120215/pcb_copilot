import sys
import argparse
from pcb_copilot.llm_engine import generate_pcb_plan
from pcb_copilot.validator import DRCValidator
from pcb_copilot.kicad_generator import KiCadGenerator, apply_auto_placement
from pcb_copilot.easyeda_generator import EasyEDAGenerator
from pcb_copilot.export_engine import ExportEngine


def main():
    parser = argparse.ArgumentParser(description="PCB-Copilot CLI: AI EDA Schematic & PCB Generator")
    parser.add_argument(
        "--prompt",
        type=str,
        default="ESP32-WROOM-32E, Ra-02 LoRa modülü, NEO-6M GPS ve 3.3V LDO içeren bir kart tasarla.",
        help="Natural language prompt describing the circuit"
    )
    parser.add_argument("--outdir", type=str, default="output", help="Output directory for generated PCB files")
    parser.add_argument("--api-key", type=str, default="", help="Gemini API Key")

    args = parser.parse_args()

    print(f"🚀 PCB-Copilot CLI - Processing prompt: '{args.prompt}'")

    # 1. Generate Netlist & Plan via Gemini LLM Engine
    plan = generate_pcb_plan(args.prompt, api_key=args.api_key)
    print(f"✅ Generated Plan: '{plan.project_title}' with {len(plan.components)} components.")

    # 2. Run DRC Validator
    validator = DRCValidator(plan)
    report = validator.run_all_checks()
    print(f"🛡️ DRC Status: Passed={report.passed} | Health Score={report.drc_score:.1f}/100")

    # 3. Apply Auto Placement
    plan = apply_auto_placement(plan)

    # 4. Generate Exports
    export_eng = ExportEngine(plan)
    zip_bytes = export_eng.build_gerber_zip_archive()

    print(f"📦 Successfully created ready-to-manufacture Gerber ZIP archive ({len(zip_bytes)} bytes)!")


if __name__ == "__main__":
    main()
