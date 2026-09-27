import os
import sys

# Ensure root directory is in sys.path when running via streamlit
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import json
import base64
import logging
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from pcb_copilot.schemas import PCBDesignPlan
from pcb_copilot.llm_engine import generate_pcb_plan
from pcb_copilot.validator import DRCValidator
from pcb_copilot.kicad_generator import KiCadGenerator, apply_auto_placement
from pcb_copilot.easyeda_generator import EasyEDAGenerator
from pcb_copilot.export_engine import ExportEngine
from pcb_copilot.config import get_api_key, DEFAULT_GEMINI_MODEL, PRO_GEMINI_MODEL

# Configure Streamlit Page
st.set_page_config(
    page_title="PCB-Copilot | AI EDA Assistant",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark Glassmorphic EDA Theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0b0f19 0%, #111827 50%, #0f172a 100%);
        color: #f8fafc;
    }
    
    /* Header Card */
    .header-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    
    /* Badge styling */
    .status-badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-success {
        background-color: rgba(16, 185, 129, 0.2);
        color: #10b981;
        border: 1px solid #10b981;
    }
    .badge-warning {
        background-color: rgba(245, 158, 11, 0.2);
        color: #f59e0b;
        border: 1px solid #f59e0b;
    }
    .badge-danger {
        background-color: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border: 1px solid #ef4444;
    }
    
    /* Code font override */
    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* Sidebar customization */
    section[data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
</style>
""", unsafe_allow_html=True)


def render_pcb_svg(plan: PCBDesignPlan) -> str:
    """
    Renders a live 2D SVG canvas visualization of the PCB layout,
    displaying component footprints, pin pads, and color-coded ratsnest wires.
    """
    bw = plan.board_width_mm
    bh = plan.board_height_mm

    # SVG Canvas dimensions
    view_width = 800
    scale = view_width / max(bw, 1.0)
    view_height = int(bh * scale)

    svg = [
        f'<svg width="100%" height="{view_height}" viewBox="0 0 {view_width} {view_height}" xmlns="http://www.w3.org/2000/svg">',
        # PCB Substrate
        f'<rect x="0" y="0" width="{view_width}" height="{view_height}" rx="12" fill="#064e3b" stroke="#10b981" stroke-width="4" />',
        f'<rect x="8" y="8" width="{view_width-16}" height="{view_height-16}" rx="8" fill="none" stroke="#047857" stroke-dasharray="4,4" stroke-width="2" />',
        f'<text x="20" y="30" fill="#34d399" font-family="JetBrains Mono" font-size="14" font-weight="bold">{plan.project_title} ({bw}x{bh} mm)</text>'
    ]

    # Map pin coordinates per net for ratsnest drawing
    net_coords = {}

    for comp in plan.components:
        cx = comp.x_mm * scale
        cy = comp.y_mm * scale
        num_pins = len(comp.pins)

        # Footprint Body size estimate
        w_mm = 16.0 if "ESP32" in comp.name else (14.0 if "Ra-02" in comp.name else (12.0 if "NEO" in comp.name else 8.0))
        h_mm = 20.0 if "ESP32" in comp.name else (14.0 if "Ra-02" in comp.name else (10.0 if "NEO" in comp.name else 6.0))

        w_px = w_mm * scale
        h_px = h_mm * scale

        # Draw component bounding box
        rect_x = cx - w_px / 2.0
        rect_y = cy - h_px / 2.0

        is_rf = "ESP32" in comp.name or "Ra-02" in comp.name
        border_color = "#f59e0b" if is_rf else "#3b82f6"
        fill_color = "rgba(245, 158, 11, 0.15)" if is_rf else "rgba(59, 130, 246, 0.15)"

        svg.append(f'<rect x="{rect_x}" y="{rect_y}" width="{w_px}" height="{h_px}" rx="4" fill="{fill_color}" stroke="{border_color}" stroke-width="2" />')

        # Draw Label
        svg.append(f'<text x="{cx}" y="{cy - h_px/2.0 - 4}" fill="#ffffff" font-family="Inter" font-size="12" font-weight="bold" text-anchor="middle">{comp.designator}: {comp.name}</text>')

        # Render Pin Pads
        for idx, pin in enumerate(comp.pins):
            if num_pins <= 4:
                px = cx + ((idx - (num_pins - 1) / 2.0) * (2.54 * scale))
                py = cy - (h_px / 2.0 - 6) if idx % 2 == 0 else cy + (h_px / 2.0 - 6)
            else:
                half = num_pins // 2
                if idx < half:
                    px = cx - w_px / 2.0 + 6
                    py = cy - (h_px / 2.0) + (idx + 1) * (h_px / (half + 1))
                else:
                    px = cx + w_px / 2.0 - 6
                    py = cy - (h_px / 2.0) + ((idx - half) + 1) * (h_px / (half + 1))

            # Pad Color by Net
            pad_color = "#ef4444" if pin.net_name in ["+3V3", "+5V"] else ("#06b6d4" if pin.net_name == "GND" else "#f59e0b")
            svg.append(f'<rect x="{px-4}" y="{py-4}" width="8" height="8" rx="2" fill="{pad_color}" stroke="#ffffff" stroke-width="1" />')
            svg.append(f'<title>{comp.designator} Pin {pin.pin_number} ({pin.pin_name}): Net {pin.net_name}</title>')

            if pin.net_name and pin.net_name != "GND":
                if pin.net_name not in net_coords:
                    net_coords[pin.net_name] = []
                net_coords[pin.net_name].append((px, py))

    # Render Ratsnest Wire Connections
    for net_name, pts in net_coords.items():
        if len(pts) > 1:
            wire_color = "#3b82f6" if net_name in ["+3V3", "+5V"] else "#a855f7"
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]
                x2, y2 = pts[i + 1]
                svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{wire_color}" stroke-width="2" stroke-dasharray="4,2" />')

    svg.append('</svg>')
    return "\n".join(svg)


def main():
    # Header Banner
    st.markdown("""
    <div class="header-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700; color: #60a5fa;">🚀 PCB-Copilot</h1>
                <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 1.05rem;">
                    Gemini API Destekli Otomatik PCB, Şematik ve Netlist Tasarım Asistanı
                </p>
            </div>
            <div>
                <span class="status-badge badge-success">Gemini 2.5 Flash / Pro Powered</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar Options
    with st.sidebar:
        st.header("⚙️ Konfigürasyon")

        env_key = get_api_key()
        api_key_input = st.text_input(
            "Gemini API Anahtarı",
            value=env_key,
            type="password",
            help="Gemini API anahtarınızı girin. Boş bırakılırsa dahili EDA kural motoru devreye girer."
        )

        model_option = st.selectbox(
            "Gemini Model Seçimi",
            options=[DEFAULT_GEMINI_MODEL, PRO_GEMINI_MODEL],
            index=0
        )

        st.divider()
        st.subheader("📐 Kart Boyutları")
        col_w, col_h = st.columns(2)
        with col_w:
            board_w = st.number_input("Genişlik (mm)", min_value=30.0, max_value=300.0, value=75.0, step=5.0)
        with col_h:
            board_h = st.number_input("Yükseklik (mm)", min_value=20.0, max_value=200.0, value=50.0, step=5.0)

        st.divider()
        st.subheader("💡 Örnek İstemler")
        if st.button("ESP32 + LoRa + GPS Taşıyıcı Kart"):
            st.session_state["circuit_prompt"] = "ESP32-WROOM-32E, Ra-02 LoRa modülü, NEO-6M GPS ve 3.3V LDO içeren bir taşıyıcı kart tasarla."
        if st.button("STM32 IoT Sensör Düğümü"):
            st.session_state["circuit_prompt"] = "STM32F103C8T6 BluePill, BME280 I2C sensörü ve NRF24L01 RF modülü içeren düşük güçlü sensör kartı."

    # Main Input Form
    default_text = st.session_state.get(
        "circuit_prompt",
        "ESP32-WROOM-32E, Ra-02 LoRa modülü, NEO-6M GPS ve 3.3V LDO içeren bir kart tasarla."
    )

    user_prompt = st.text_area(
        "💬 Devre Gereksinimlerinizi Doğal Dille Tanımlayın:",
        value=default_text,
        height=100,
        help="Tasarlamak istediğiniz devre bileşenlerini, voltaj gereksinimlerini ve veri hatlarını yazın."
    )

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        generate_clicked = st.button("✨ Devreyi Oluştur", type="primary", use_container_width=True)

    if generate_clicked or "current_plan" in st.session_state:
        if generate_clicked or "current_plan" not in st.session_state:
            with st.spinner("Gemini API devrenizi analiz ediyor, Netlist ve DRC kontrollerini hazırlıyor..."):
                plan = generate_pcb_plan(
                    prompt=user_prompt,
                    api_key=api_key_input,
                    model_name=model_option
                )
                plan.board_width_mm = board_w
                plan.board_height_mm = board_h

                # Auto placement
                plan = apply_auto_placement(plan)

                # Validate DRC
                validator = DRCValidator(plan)
                drc_report = validator.run_all_checks()

                st.session_state["current_plan"] = plan
                st.session_state["current_drc"] = drc_report

        plan: PCBDesignPlan = st.session_state["current_plan"]
        drc_report = st.session_state["current_drc"]

        # Main Tabs
        tab_layout, tab_netlist, tab_drc, tab_export = st.tabs([
            "🖥️ 2D PCB Görselleştirici",
            "📋 Malzeme Listesi (BOM) & Netlist",
            "🛡️ DRC & Voltaj Doğrulama",
            "📦 Dışa Aktar (KiCad / EasyEDA / Gerber)"
        ])

        # TAB 1: 2D Visualizer
        with tab_layout:
            st.subheader(f"📌 {plan.project_title} (Otomatik Yerleşim ve Hatlar)")
            svg_content = render_pcb_svg(plan)
            st.components.v1.html(svg_content, height=int(plan.board_height_mm * (800 / plan.board_width_mm)) + 20)

            st.info("💡 **Renk Kodları:** 🔴 Kırmızı/Turuncu = +3V3/+5V Güç | 🔵 Mavi/Mor = Sinyal Hatları | 🌐 Turkuaz = GND Pads")

        # TAB 2: BOM & Netlist
        with tab_netlist:
            col_bom, col_notes = st.columns([3, 2])

            with col_bom:
                st.subheader("📦 Bileşen Listesi (BOM)")
                bom_data = []
                for c in plan.components:
                    bom_data.append({
                        "Referans": c.designator,
                        "Bileşen Adı": c.name,
                        "Değer": c.value or "-",
                        "Kılıf (Footprint)": c.footprint,
                        "Pin Sayısı": len(c.pins),
                        "Konum (X, Y)": f"{c.x_mm}, {c.y_mm} mm"
                    })
                st.dataframe(bom_data, use_container_width=True)

            with col_notes:
                st.subheader("📝 Tasarım Notları & Kurallar")
                for note in plan.design_notes:
                    st.markdown(f"- {note}")

            st.divider()
            st.subheader("🔌 Detaylı Pin / Net Bağlantı Şeması")
            net_tree = {}
            for c in plan.components:
                for p in c.pins:
                    if p.net_name:
                        if p.net_name not in net_tree:
                            net_tree[p.net_name] = []
                        net_tree[p.net_name].append(f"{c.designator}.{p.pin_number} ({p.pin_name})")

            st.json(net_tree)

        # TAB 3: DRC Report
        with tab_drc:
            st.subheader("🛡️ Otomatik DRC & Mantıksal Kontrol Raporu")

            score = drc_report.drc_score
            badge_class = "badge-success" if score > 80 else ("badge-warning" if score > 50 else "badge-danger")
            st.markdown(
                f'<h4>Sağlık Skoru: <span class="status-badge {badge_class}">{score:.1f} / 100</span></h4>',
                unsafe_allow_html=True
            )

            if drc_report.passed:
                st.success("✅ Tebrikler! Devre herhangi bir kritik kısa devre veya eksik güç hatası içermiyor.")
            else:
                st.error("⚠️ Dikkat! Devrenizde düzeltilmesi gereken DRC çakışmaları tespit edildi.")

            if drc_report.voltage_conflicts:
                st.error("🚨 Voltaj Çakışmaları / Kısa Devre:")
                for err in drc_report.voltage_conflicts:
                    st.write(f"- **[{err.severity}]** {err.message}")

            if drc_report.unconnected_power_pins:
                st.warning("⚡ Eksik Güç Bağlantıları:")
                for err in drc_report.unconnected_power_pins:
                    st.write(f"- {err.message}")

            if drc_report.missing_decoupling:
                st.info("🔋 Dekuplaj Kondansatörü Önerileri:")
                for err in drc_report.missing_decoupling:
                    st.write(f"- {err.message}")

            if drc_report.warnings:
                st.info("💡 Tasarım Tavsiyeleri:")
                for err in drc_report.warnings:
                    st.write(f"- {err.message}")

        # TAB 4: Exports
        with tab_export:
            st.subheader("📦 Üretime Hazır Çıktıları İndir")
            st.write("Tasarlanan devrenizi KiCad, EasyEDA veya Gerber formatında tek tıkla bilgisayarınıza indirin.")

            export_eng = ExportEngine(plan)
            zip_bytes = export_eng.build_gerber_zip_archive()

            kicad_gen = KiCadGenerator(plan)
            kicad_pcb_str = kicad_gen.generate_kicad_pcb()
            kicad_sch_str = kicad_gen.generate_kicad_sch()

            easyeda_gen = EasyEDAGenerator(plan)
            easyeda_json_str = easyeda_gen.generate_easyeda_json_string()

            col_ex1, col_ex2, col_ex3, col_ex4 = st.columns(4)

            with col_ex1:
                st.download_button(
                    label="💾 KiCad PCB (.kicad_pcb)",
                    data=kicad_pcb_str,
                    file_name="circuit.kicad_pcb",
                    mime="text/plain",
                    use_container_width=True
                )

            with col_ex2:
                st.download_button(
                    label="📄 KiCad Şematik (.kicad_sch)",
                    data=kicad_sch_str,
                    file_name="circuit.kicad_sch",
                    mime="text/plain",
                    use_container_width=True
                )

            with col_ex3:
                st.download_button(
                    label="🌐 EasyEDA JSON (.json)",
                    data=easyeda_json_str,
                    file_name="easyeda_pcb.json",
                    mime="application/json",
                    use_container_width=True
                )

            with col_ex4:
                st.download_button(
                    label="📦 Gerber Paketi (.zip)",
                    data=zip_bytes,
                    file_name="gerber_pack.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True
                )


if __name__ == "__main__":
    main()
