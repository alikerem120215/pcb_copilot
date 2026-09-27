# 🚀 PCB-Copilot — LLM Destekli KiCad & EasyEDA Devre Tasarım Asistanı

PCB-Copilot; elektronik mühendisleri ve maker'lar için doğal dille ifade edilen devre tasarımlarını (örn: *"ESP32-WROOM-32, USB-C şarj, LoRa modülü ve I2C OLED ekran içeren bir kart tasarla"*) anlayarak otomatik **KiCad Şeması**, **EasyEDA JSON** ve **Gerber/BOM** paketleri üreten yapay zeka destekli EDA asistanıdır.

---

## 🌟 Mimari ve Yetenekler

- **LLM Tasarım Motoru (`llm_engine.py`):** Google Gemini Pro / Flash modellerini kullanarak devre bloklarını, pin netlistlerini ve komponent seçimlerini Pydantic şemasıyla doğrular.
- **DRC Doğrulayıcı (`validator.py`):** Oluşturulan şematik ağları (netleri) elektriksel kurallara, voltaj uyumsuzluklarına ve floating pinlere karşı otomatik denetler.
- **KiCad Jeneratörü (`kicad_generator.py`):** KiCad v7/v8 formatında `.kicad_sch` şematik dosyaları üretir ve temel yerleşim algoritması (`auto_placement`) uygular.
- **EasyEDA Entegrasyonu (`easyeda_generator.py`):** Web üzerinde çalışan EasyEDA editörüne doğrudan içe aktarılabilir standart JSON formatı oluşturur.
- **Dışa Aktarma Paketi (`export_engine.py`):** Netlist raporu, Malzeme Listesi (BOM.csv) ve Gerber zip arşivi çıktısı üretir.
- **Modern Streamlit Arayüzü (`app.py`):** Matplotlib destekli kart önizlemesi ve interaktif tasarım paneli.

---

## 🛠️ Kurulum & Çalıştırma

```bash
cd pcb_copilot
pip install -r requirements.txt
streamlit run pcb_copilot/app.py
```
