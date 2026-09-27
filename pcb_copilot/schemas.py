from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class PinConnection(BaseModel):
    pin_number: str = Field(description="Bileşenin fiziksel pin numarası (Örn: 1, 38, VCC)")
    pin_name: str = Field(description="Pinin fonksiyonel adı (Örn: GPIO5, VCC, GND, MOSI, TXD, RXD)")
    net_name: str = Field(description="Bağlandığı hat (Net) adı (Örn: SPI_MOSI, +3V3, GND, UART_TX)")


class Component(BaseModel):
    designator: str = Field(description="Referans kodu (Örn: U1, U2, R1, C1, C2, J1)")
    name: str = Field(description="Bileşen adı (Örn: ESP32-WROOM-32E, Ra-02, NEO-6M, AMS1117-3.3)")
    footprint: str = Field(description="Standart KiCad / EasyEDA kılıf kütüphane adı (Örn: RF_Module:ESP32-WROOM-32, Resistor_SMD:R_0805_2012Metric)")
    value: Optional[str] = Field(None, description="Değer veya Spesifikasyon (Örn: 10k, 100nF, 10uF, 3.3V)")
    pins: List[PinConnection] = Field(default_factory=list)
    x_mm: float = Field(default=0.0, description="PCB üzerindeki X koordinatı (mm)")
    y_mm: float = Field(default=0.0, description="PCB üzerindeki Y koordinatı (mm)")
    rotation_deg: float = Field(default=0.0, description="Açı dönmesi (derece)")
    layer: str = Field(default="F.Cu", description="Yerleştiği katman (F.Cu top, B.Cu bottom)")


class PCBDesignPlan(BaseModel):
    project_title: str = Field(description="Projenin başlığı ve kısa açıklaması")
    board_width_mm: float = Field(default=65.0, description="PCB kart genişliği (mm)")
    board_height_mm: float = Field(default=45.0, description="PCB kart yüksekliği (mm)")
    components: List[Component] = Field(default_factory=list, description="Kart üzerindeki tüm bileşenler")
    design_notes: List[str] = Field(default_factory=list, description="RF keepout, hat kalınlıkları, dekuplaj uyarısı ve kritik EDA tasarım kuralları")


class DRCError(BaseModel):
    error_type: str = Field(description="Hata türü (Kısa Devre, Açık Hat, Eksik Güç, Sınır İhlali vb.)")
    severity: str = Field(default="ERROR", description="Ciddiyet seviyesi: ERROR, WARNING, INFO")
    message: str = Field(description="Açıklayıcı hata mesajı")
    components_involved: List[str] = Field(default_factory=list, description="İlgili bileşen referansları")
    nets_involved: List[str] = Field(default_factory=list, description="İlgili hat (net) adları")


class DRCReport(BaseModel):
    passed: bool = Field(description="DRC doğrulamasının başarıyla geçip geçmediği")
    voltage_conflicts: List[DRCError] = Field(default_factory=list)
    unconnected_power_pins: List[DRCError] = Field(default_factory=list)
    missing_decoupling: List[DRCError] = Field(default_factory=list)
    pin_clashes: List[DRCError] = Field(default_factory=list)
    board_bounds_errors: List[DRCError] = Field(default_factory=list)
    warnings: List[DRCError] = Field(default_factory=list)
    drc_score: float = Field(default=100.0, description="Sağlık ve DRC skoru (0-100)")
