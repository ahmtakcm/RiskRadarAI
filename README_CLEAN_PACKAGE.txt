RiskRadarAI clean full package

İçerik:
- Çalışan proje dosyaları korunmuştur.
- Eski .bak / .pre / .before patch kalıntıları çıkarılmıştır.
- Windows tekil-instance kilidi eklendi: single_instance.py + main.py wrapper.
- start_bot.bat ikinci kopya başlatmayı engelleyecek şekilde güncellendi.
- storage/runtime_state.json temiz pakete konmadı; mevcut kurulumda eski state'i korumak istiyorsanız klasörü komple silmeden üstüne çıkarın.
- cleanup_old_files.ps1 eski gereksiz dosyaları temizlemek içindir; .env ve runtime_state.json'a dokunmaz.
