import logging
from typing import List, Dict, Set
from pcb_copilot.schemas import PCBDesignPlan, DRCReport, DRCError
from pcb_copilot.config import POWER_NETS_3V3, POWER_NETS_5V, GROUND_NETS

logger = logging.getLogger(__name__)


class DRCValidator:
    """
    Design Rule Check (DRC) & Voltage level validator for PCB-Copilot.
    """

    def __init__(self, plan: PCBDesignPlan):
        self.plan = plan

    def run_all_checks(self) -> DRCReport:
        """Run all rule checks and compile a comprehensive DRC report."""
        voltage_conflicts = self._check_voltage_conflicts()
        unconnected_power = self._check_unconnected_power_pins()
        missing_decoupling = self._check_decoupling_capacitors()
        pin_clashes = self._check_pin_clashes()
        bounds_errors = self._check_board_bounds()
        warnings = self._generate_design_warnings()

        has_critical_errors = len(voltage_conflicts) > 0 or len(unconnected_power) > 0 or len(bounds_errors) > 0
        passed = not has_critical_errors

        # Calculate health score (100 base, subtract for errors/warnings)
        error_penalty = (len(voltage_conflicts) * 25) + (len(unconnected_power) * 15) + (len(bounds_errors) * 10)
        warning_penalty = (len(missing_decoupling) * 5) + (len(pin_clashes) * 5) + (len(warnings) * 2)
        drc_score = max(0.0, min(100.0, 100.0 - error_penalty - warning_penalty))

        report = DRCReport(
            passed=passed,
            voltage_conflicts=voltage_conflicts,
            unconnected_power_pins=unconnected_power,
            missing_decoupling=missing_decoupling,
            pin_clashes=pin_clashes,
            board_bounds_errors=bounds_errors,
            warnings=warnings,
            drc_score=drc_score
        )
        return report

    def _check_voltage_conflicts(self) -> List[DRCError]:
        """Detect short circuits between incompatible power rails (+5V, +3V3, GND)."""
        errors = []
        for comp in self.plan.components:
            # Build net mapping for this component's pins
            nets_on_comp = set()
            for pin in comp.pins:
                nets_on_comp.add(pin.net_name)

            has_3v3 = any(net in POWER_NETS_3V3 for net in nets_on_comp)
            has_5v = any(net in POWER_NETS_5V for net in nets_on_comp)
            has_gnd = any(net in GROUND_NETS for net in nets_on_comp)

            # Allow power regulators, level shifters, and power headers/connectors to carry multiple power rails
            is_power_interface = any(
                kw in comp.name.lower() or kw in comp.designator.lower()
                for kw in ["ams1117", "ldo", "regulator", "level_shifter", "header", "connector", "j1", "jack", "plug"]
            )
            if not is_power_interface:
                if has_3v3 and has_5v:
                    errors.append(DRCError(
                        error_type="Kısa Devre / Voltaj Çakışması",
                        severity="ERROR",
                        message=f"Bileşen '{comp.designator}' ({comp.name}) hem +3V3 hem de +5V hattına regülatörsüz bağlanmış!",
                        components_involved=[comp.designator],
                        nets_involved=["+3V3", "+5V"]
                    ))
                if has_3v3 and has_gnd and len(comp.pins) <= 2 and "cap" not in comp.name.lower():
                    # If a resistor connects +3V3 and GND directly (0 ohm or missing value)
                    if comp.value in ["0", "0R", "0 ohm"]:
                        errors.append(DRCError(
                            error_type="Güç Kısa Devresi",
                            severity="ERROR",
                            message=f"Bileşen '{comp.designator}' +3V3 ile GND arasında 0 Ohm köprü oluşturuyor!",
                            components_involved=[comp.designator],
                            nets_involved=["+3V3", "GND"]
                        ))
        return errors

    def _check_unconnected_power_pins(self) -> List[DRCError]:
        """Ensure active ICs (U1, U2...) have both VCC (+3V3 or +5V) and GND connected."""
        errors = []
        for comp in self.plan.components:
            if comp.designator.startswith("U"):
                nets = {pin.net_name for pin in comp.pins}

                has_vcc = any(net in POWER_NETS_3V3 or net in POWER_NETS_5V for net in nets)
                has_gnd = any(net in GROUND_NETS for net in nets)

                if not has_vcc:
                    errors.append(DRCError(
                        error_type="Eksik VCC Bağlantısı",
                        severity="ERROR",
                        message=f"Aktif entegre '{comp.designator}' ({comp.name}) için besleme voltajı (VCC) pini tanımlanmamış!",
                        components_involved=[comp.designator],
                        nets_involved=list(nets)
                    ))

                if not has_gnd:
                    errors.append(DRCError(
                        error_type="Eksik Toprak (GND) Bağlantısı",
                        severity="ERROR",
                        message=f"Aktif entegre '{comp.designator}' ({comp.name}) için toprak (GND) pini tanımlanmamış!",
                        components_involved=[comp.designator],
                        nets_involved=list(nets)
                    ))
        return errors

    def _check_decoupling_capacitors(self) -> List[DRCError]:
        """Check if active ICs have nearby decoupling capacitors on power rails."""
        errors = []
        active_ics = [c for c in self.plan.components if c.designator.startswith("U") and "ams1117" not in c.name.lower()]
        decoupling_caps = [c for c in self.plan.components if c.name.lower() in ["capacitor", "c"] and c.value in ["100nF", "0.1uF"]]

        if len(active_ics) > len(decoupling_caps):
            errors.append(DRCError(
                error_type="Eksik Dekuplaj Kapasitörü",
                severity="WARNING",
                message=f"Kartta {len(active_ics)} aktif entegre var fakat sadece {len(decoupling_caps)} adet 100nF dekuplaj kondansatörü bulundu. Parazit önleme için her IC'ye 100nF önerilir.",
                components_involved=[c.designator for c in active_ics],
                nets_involved=["+3V3", "GND"]
            ))
        return errors

    def _check_pin_clashes(self) -> List[DRCError]:
        """Check for pin number duplicates or ambiguous net connections."""
        errors = []
        for comp in self.plan.components:
            pin_numbers = [p.pin_number for p in comp.pins]
            if len(pin_numbers) != len(set(pin_numbers)):
                # duplicate pin numbers
                seen = set()
                dups = set()
                for p in pin_numbers:
                    if p in seen:
                        dups.add(p)
                    seen.add(p)
                errors.append(DRCError(
                    error_type="Çift Pin Numarası",
                    severity="WARNING",
                    message=f"Bileşen '{comp.designator}' aynı pin numarasına ({', '.join(dups)}) birden fazla bağlantı içeriyor.",
                    components_involved=[comp.designator]
                ))
        return errors

    def _check_board_bounds(self) -> List[DRCError]:
        """Check if component coordinates fall outside PCB boundaries."""
        errors = []
        bw = self.plan.board_width_mm
        bh = self.plan.board_height_mm

        for comp in self.plan.components:
            if comp.x_mm < 0 or comp.x_mm > bw or comp.y_mm < 0 or comp.y_mm > bh:
                # Note: Coordinates might be set during auto-placement phase
                if comp.x_mm != 0.0 or comp.y_mm != 0.0:
                    errors.append(DRCError(
                        error_type="Kart Sınır İhlali",
                        severity="ERROR",
                        message=f"Bileşen '{comp.designator}' koordinatları ({comp.x_mm:.1f}, {comp.y_mm:.1f}) mm kart sınırları ({bw}x{bh} mm) dışında!",
                        components_involved=[comp.designator]
                    ))
        return errors

    def _generate_design_warnings(self) -> List[DRCError]:
        """General high-speed/RF design warnings."""
        warnings = []
        rf_components = [c for c in self.plan.components if "lora" in c.name.lower() or "esp32" in c.name.lower() or "gps" in c.name.lower()]
        if rf_components:
            warnings.append(DRCError(
                error_type="RF Anten Yerleşim Uyarısı",
                severity="INFO",
                message=f"Kartta RF modülleri ({', '.join([c.designator for c in rf_components])}) var. Anten altında bakar dolgusu (ground copper) bırakmayın (Keepout Zone).",
                components_involved=[c.designator for c in rf_components]
            ))
        return warnings
