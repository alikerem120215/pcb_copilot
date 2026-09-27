import os

# Gemini Model Settings
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
PRO_GEMINI_MODEL = "gemini-2.5-pro"

# System Environment Variable for API key
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"

# PCB Layout Grid & Dimensions Defaults
DEFAULT_BOARD_WIDTH_MM = 65.0
DEFAULT_BOARD_HEIGHT_MM = 45.0
GRID_SIZE_MM = 2.54  # 100 mil grid
EDGE_MARGIN_MM = 5.0

# Recognized Standard Voltage Nets
POWER_NETS_3V3 = {"+3V3", "3V3", "+3.3V", "3.3V", "VCC_3V3"}
POWER_NETS_5V = {"+5V", "5V", "VCC_5V", "USB_5V", "VIN_5V"}
GROUND_NETS = {"GND", "DGND", "AGND", "0V", "GND_POWER"}

# Footprint Mapping Helpers for KiCad & EasyEDA
FOOTPRINT_LIBRARY = {
    "ESP32-WROOM-32E": {
        "kicad": "RF_Module:ESP32-WROOM-32",
        "easyeda": "MODULE-ESP32-WROOM-32",
        "width_mm": 18.0,
        "height_mm": 25.5,
        "pin_count": 38
    },
    "ESP32": {
        "kicad": "RF_Module:ESP32-WROOM-32",
        "easyeda": "MODULE-ESP32-WROOM-32",
        "width_mm": 18.0,
        "height_mm": 25.5,
        "pin_count": 38
    },
    "Ra-02": {
        "kicad": "RF_Module:Ai-Thinker-Ra-02",
        "easyeda": "MODULE-RA-02",
        "width_mm": 17.0,
        "height_mm": 16.0,
        "pin_count": 16
    },
    "NEO-6M": {
        "kicad": "RF_GPS:NEO-6M",
        "easyeda": "MODULE-NEO-6M",
        "width_mm": 16.0,
        "height_mm": 12.2,
        "pin_count": 4
    },
    "AMS1117-3.3": {
        "kicad": "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
        "easyeda": "SOT-223-3",
        "width_mm": 6.5,
        "height_mm": 3.5,
        "pin_count": 4
    },
    "Resistor": {
        "kicad": "Resistor_SMD:R_0805_2012Metric",
        "easyeda": "R0805",
        "width_mm": 2.0,
        "height_mm": 1.25,
        "pin_count": 2
    },
    "Capacitor": {
        "kicad": "Capacitor_SMD:C_0805_2012Metric",
        "easyeda": "C0805",
        "width_mm": 2.0,
        "height_mm": 1.25,
        "pin_count": 2
    },
    "Header_1x4": {
        "kicad": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
        "easyeda": "HDR-TH_4P-P2.54",
        "width_mm": 10.16,
        "height_mm": 2.54,
        "pin_count": 4
    }
}


def get_api_key() -> str:
    """Retrieve Gemini API key from environment variable if available."""
    return os.environ.get(GEMINI_API_KEY_ENV, "")
