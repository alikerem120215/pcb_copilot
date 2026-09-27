import os
import sys
import unittest

# Ensure pcb_copilot package is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pcb_copilot.schemas import PCBDesignPlan, Component, PinConnection, DRCReport
from pcb_copilot.llm_engine import generate_pcb_plan
from pcb_copilot.validator import DRCValidator
from pcb_copilot.kicad_generator import KiCadGenerator, apply_auto_placement
from pcb_copilot.easyeda_generator import EasyEDAGenerator
from pcb_copilot.export_engine import ExportEngine


class TestPCBCopilot(unittest.TestCase):
    """
    Comprehensive Integration Test for PCB-Copilot AI Agent.
    """

    def setUp(self):
        self.sample_prompt = "ESP32-WROOM-32E, Ra-02 LoRa modülü, NEO-6M GPS ve 3.3V LDO içeren bir taşıyıcı kart tasarla."

    def test_1_llm_engine_plan_generation(self):
        """Test generation of PCBDesignPlan schema from natural language prompt."""
        print("\n--- Test 1: LLM Engine Generation ---")
        plan = generate_pcb_plan(self.sample_prompt)

        self.assertIsInstance(plan, PCBDesignPlan)
        self.assertGreater(len(plan.components), 0)
        print(f"✅ Generated Plan Title: {plan.project_title}")
        print(f"✅ Total Components: {len(plan.components)}")

        # Verify key required components exist
        designators = [c.designator for c in plan.components]
        names = [c.name for c in plan.components]

        self.assertTrue(any("ESP32" in name for name in names), "ESP32 component missing")
        self.assertTrue(any("LoRa" in name or "Ra-02" in name for name in names), "LoRa component missing")
        self.assertTrue(any("GPS" in name or "NEO-6M" in name for name in names), "GPS component missing")
        self.assertTrue(any("AMS1117" in name or "LDO" in name for name in names), "LDO regulator missing")

    def test_2_drc_validator(self):
        """Test DRC and Voltage short circuit check engine."""
        print("\n--- Test 2: DRC & Rule Validator ---")
        plan = generate_pcb_plan(self.sample_prompt)
        validator = DRCValidator(plan)
        report = validator.run_all_checks()

        self.assertIsInstance(report, DRCReport)
        print(f"✅ DRC Passed: {report.passed}")
        print(f"✅ DRC Health Score: {report.drc_score:.1f} / 100")
        print(f"✅ Voltage Conflicts: {len(report.voltage_conflicts)}")
        print(f"✅ Unconnected Power Pins: {len(report.unconnected_power_pins)}")

        self.assertEqual(len(report.voltage_conflicts), 0, "No voltage short circuits should exist in generated design!")

    def test_3_auto_placement_and_kicad_generation(self):
        """Test component auto-placement and native KiCad .kicad_pcb S-expression output."""
        print("\n--- Test 3: KiCad PCB Generator ---")
        plan = generate_pcb_plan(self.sample_prompt)
        plan = apply_auto_placement(plan)

        kicad_gen = KiCadGenerator(plan)
        pcb_text = kicad_gen.generate_kicad_pcb()
        sch_text = kicad_gen.generate_kicad_sch()

        self.assertIn("(kicad_pcb", pcb_text)
        self.assertIn('layer "Edge.Cuts"', pcb_text)
        self.assertIn('(kicad_sch', sch_text)
        print(f"✅ Generated KiCad PCB text length: {len(pcb_text)} bytes")

    def test_4_easyeda_generation(self):
        """Test EasyEDA PCB JSON output."""
        print("\n--- Test 4: EasyEDA JSON Generator ---")
        plan = generate_pcb_plan(self.sample_prompt)
        easy_gen = EasyEDAGenerator(plan)
        easy_json = easy_gen.generate_easyeda_json()

        self.assertIn("head", easy_json)
        self.assertIn("components", easy_json)
        self.assertGreater(len(easy_json["components"]), 0)
        print(f"✅ Generated EasyEDA JSON components count: {len(easy_json['components'])}")

    def test_5_export_gerber_zip(self):
        """Test Gerber RS-274X layer packaging and ZIP generation."""
        print("\n--- Test 5: Gerber & Export Engine ---")
        plan = generate_pcb_plan(self.sample_prompt)
        export_eng = ExportEngine(plan)
        zip_bytes = export_eng.build_gerber_zip_archive()

        self.assertGreater(len(zip_bytes), 500, "Gerber ZIP archive should contain valid bytes")
        print(f"✅ Gerber ZIP archive created successfully! ({len(zip_bytes)} bytes)")


if __name__ == "__main__":
    unittest.main()
