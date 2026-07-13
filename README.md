<p align="center">
  <img src="assets/icon.png" width="120" alt="Teufort Toolkit" />
</p>

<h1 align="center">Teufort Toolkit</h1>

<p align="center">
  All-in-one desktop utility for Team Fortress 2 — <b>spray maker</b>,
  full-color <b>Conscientious Objector</b> image maker and
  <b>hitsound / killsound</b> trimmer. With in-game previews, in one modern UI.
  <br>
  <i>Team Fortress 2 için hepsi bir arada masaüstü aracı — sprey oluşturucu,
  tam renkli Conscientious Objector resmi yapıcı ve hitsound / killsound kesici.</i>
</p>

<p align="center">
  <i>Windows &nbsp;•&nbsp; Python + CustomTkinter &nbsp;•&nbsp; single <code>.exe</code>, no install &nbsp;•&nbsp; 9 languages</i>
</p>

<p align="center">
  <img src="assets/screenshot.png" width="760" alt="Teufort Toolkit screenshot" />
</p>

<p align="center">
  <b>English</b> &nbsp;·&nbsp; <a href="#türkçe">Türkçe</a>
</p>

---

<a id="english"></a>

## ✨ Features

- 🎨 **Spray Maker** — turns an image/GIF into a `.vtf` + `.vmt` spray,
  auto-optimizes to stay under the 512 KB limit, and shows a real "in-game"
  preview using genuine DXT compression.
- 🖼️ **Objector Maker** — creates a full-color `paper_overlay.png` for the
  Conscientious Objector, with a live crop preview and a picket-sign mockup.
- 🔊 **Hitsound Trimmer** — trims audio on a waveform and saves it as a
  TF2-standard (44100 Hz, 16-bit) `hitsound.wav` / `killsound.wav`.
- 📁 **Automatic TF2 detection** — finds the `tf` folder via the registry and
  Steam libraries; each module has its own export-path setting that persists.
- 🌐 **9 languages** — Türkçe, English, Русский, Español, Deutsch, Français,
  한국어, Português, 中文. Switch from the menu at the top-right (the app
  reopens in the chosen language); your choice is saved to `config.json`.

## 🚀 Installation

### Option A — Prebuilt .exe (recommended, no Python needed)

1. Go to the **[Releases](../../releases)** section.
2. Download **`Teufort Toolkit.exe`** from the latest release.
3. Double-click it — nothing else to install.

> **Windows SmartScreen warning:** because the app is unsigned, Windows may say
> "Unknown publisher". Open it with **More info → Run anyway**. The first launch
> takes a few seconds (a onefile exe unpacks itself to a temp folder).

### Option B — Run from source (for developers)

Requires **Python 3.10+** (Windows).

```bash
git clone https://github.com/Scainest/Teufort-Toolkit.git
cd Teufort-Toolkit
pip install -r requirements.txt
python main.py
```

## 📖 Usage

On launch the app auto-detects your TF2 folder. If it can't, use **📁 Choose
Manually** to point at `...\Team Fortress 2\tf`. Each tab has its own **Export
folder** + **Browse**; settings are saved to `config.json`.

### 🎨 Spray Maker

<p align="center">
  <img src="assets/spray-preview.png" width="720" alt="Spray Maker — in-game preview" />
</p>

1. **Choose Image** (`.png / .jpg / .gif`) — animated GIFs are supported. New
   here? Click **🧪 Example** to load the bundled sample image in one click.
2. Set a spray name and max resolution (512/256/128).
3. Switch to **In-Game (VTF)** to see how the spray will really look in game
   (including DXT compression).
4. Set the **Export folder** to `...\tf\materials\vgui\logos` and **Create Spray**.
5. In game: pick it from **Settings → Multiplayer → Spray**.

If the output exceeds 512 KB, resolution and (for GIFs) frame count are reduced
automatically.

### 🖼️ Objector Maker (Full-Color Conscientious Objector)

1. **Choose Image**, drag/resize the square crop area — the output and sign
   preview update instantly.
2. **Resolution**: `256 (recommended)` / `128 (most compatible)` / `512 (sharpest)`.
3. Set the **Export folder** to your custom folder (e.g. `...\tf\custom\MyMod`).
   The file is written to the correct path automatically:
   `scripts\items\custom_texture_blend_layers\paper_overlay.png`
4. **Fully close TF2**, create the file, launch the game and apply
   `paper_overlay` to the Conscientious Objector with the **Decal Tool**.

> ⚠️ This uses the Source engine's asynchronous texture loading and sometimes
> doesn't show right away. If it doesn't, set the resolution to **128**, update
> your GPU drivers, add a fixed `-dxlevel` launch option, and restart TF2.
> Note: the `materials\...` path **does not work** — the file must be under
> `scripts\items\...`.

### 🔊 Hitsound Trimmer

1. **Choose Audio File** (`.mp3 / .wav / .ogg / .flac`).
2. Pick start/end with the orange handles on the waveform, **▶ Preview** to listen.
3. Set the **Export folder** to your custom folder.
4. **🎯 Export as Hitsound** or **💀 Export as Killsound** — saved to
   `sound\ui\hitsound.wav` / `sound\ui\killsound.wav` respectively.

> For the hitsound to work, enable **Options → Advanced → "Play a hit sound"** in game.

## 🛠️ Building the .exe from source

```bash
pip install -r requirements.txt pyinstaller
python assets/make_icon.py
```

Then run `build.bat` **or** this command:

```bash
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name "Teufort Toolkit" --icon "assets\icon.ico" ^
  --add-data "assets\icon.ico;assets" ^
  --add-data "assets\samples;assets\samples" ^
  --collect-all customtkinter --collect-all soundfile --collect-all sounddevice ^
  --exclude-module scipy main.py
```

Output: `dist\Teufort Toolkit.exe` (~31 MB). Notes:
- `scipy` is excluded on purpose (~100 MB saved); audio resampling uses the
  pure-numpy windowed-sinc filter in `core/audio.py` (≈85 dB SNR).
- When frozen (exe), `config.json` is stored under `%APPDATA%\TeufortToolkit\`.

## 🧪 Tests

```bash
python tests/test_core.py       # core validation (VTF parser + DXT decoder)
python tests/test_gui_smoke.py  # end-to-end GUI smoke test across all three tabs
```

## 📂 Project structure

```
main.py            # entry point
config.py          # config.json handling (source vs exe)
tf2_locator.py     # TF2 auto-detection (registry + libraryfolders.vdf)
i18n.py            # 9-language UI translations
resources.py       # bundled-resource path helper (source/exe)
core/
  vtf.py           # VTF 7.1 writer + numpy DXT1/DXT5 encoder/decoder
  spray.py         # spray pipeline (size/frame planner, VMT)
  objector.py      # paper_overlay generation
  preview.py       # in-game previews (DXT round-trip, wall, sign)
  audio.py         # trim + resample + WAV export
  paths.py         # path-duplication guard
gui/
  app.py           # main window, tabs, TF2 status, language picker
  widgets.py       # PathSelector, CropCanvas, WaveformCanvas
  spray_tab.py / objector_tab.py / sound_tab.py
assets/            # icon generator + bundled sample image
tests/             # core + GUI tests
```

## ❓ Troubleshooting

- **"TF2 not found"** → Use **📁 Choose Manually** to point at `...\Team Fortress 2\tf`.
- **Spray not showing in game** → Make sure the output is in `tf\materials\vgui\logos`
  and selected in game.
- **Objector isn't full color** → The file must be under
  `scripts\items\custom_texture_blend_layers`; try resolution 128 and restart TF2.
- **MP3 won't open** → The app ships with libsndfile; if it still fails, convert
  the file to `.wav`.

## ⚠️ "Windows protected your PC" (SmartScreen)

On first run Windows may show **"Unknown publisher / Windows protected your PC"**.
To open it: **More info → Run anyway**.

**This is not a virus warning.** It appears for **every** new app that isn't
signed with a (paid) *code-signing certificate* and hasn't been downloaded
enough yet — Windows is just saying "I don't recognize this publisher yet".

Why you can trust it:
- **The full source is open** — inspect it or build the same exe yourself with
  `build.bat`.
- The app only writes to **the folders you pick**; it doesn't install anything,
  run in the background, or send data online.

**Antivirus false positives:** PyInstaller onefile exes sometimes trip 1–4
heuristic scanners (labelled `Riskware.PyInstaller` etc.) because they unpack to
a temp folder — this is normal and harmless; major engines (Microsoft Defender,
Kaspersky, BitDefender, ESET, Avast…) are clean. Each release's **SHA-256** is on
its release page so you can verify the download with
`Get-FileHash "Teufort Toolkit.exe" -Algorithm SHA256`.

To remove the warning entirely you'd need to **sign the exe** with a code-signing
certificate (EV cert = instant SmartScreen trust but pricey; Azure Trusted
Signing ~$10/mo; SignPath's free plan for open-source), or let SmartScreen
reputation build over time.

## 📜 License

[MIT](LICENSE) — use, modify and distribute freely. This is a fan-made tool and
is not affiliated with or endorsed by Valve.

---

<a id="türkçe"></a>

## 🇹🇷 Türkçe

[English](#english) yukarıda.

### ✨ Özellikler

- 🎨 **Sprey Oluşturucu** — resim/GIF'i `.vtf` + `.vmt` spreye çevirir, 512 KB
  sınırına göre otomatik optimize eder, gerçek DXT sıkıştırmasıyla "oyun içi"
  önizleme gösterir.
- 🖼️ **Objector Maker** — Conscientious Objector için tam renkli
  `paper_overlay.png` üretir, canlı kırpma önizlemesi ve tabela maketi ile.
- 🔊 **Hitsound Kesici** — sesi dalga formu üzerinden kırpar, TF2 standardı
  (44100 Hz, 16-bit) `hitsound.wav` / `killsound.wav` olarak kaydeder.
- 📁 **Otomatik TF2 tespiti** — `tf` klasörünü kayıt defteri ve Steam
  kütüphanelerinden bulur; her modülün kendi kayıt yolu ayarı vardır ve kalıcı
  olarak saklanır.
- 🌐 **9 dil** — Türkçe, English, Русский, Español, Deutsch, Français, 한국어,
  Português, 中文. Sağ üstteki menüden dili değiştirin (uygulama seçilen dilde
  yeniden açılır); tercih `config.json`'a kaydedilir.

### 🚀 Kurulum

**Seçenek A — Hazır .exe (önerilen, Python gerekmez)**

1. **[Releases](../../releases)** bölümüne git.
2. En son sürümden **`Teufort Toolkit.exe`** dosyasını indir.
3. Çift tıkla — çalıştırmak için başka bir şey yüklemene gerek yok.

> **Windows SmartScreen uyarısı:** İmzasız bir uygulama olduğu için Windows
> "Bilinmeyen yayımcı" diyebilir. **Ek bilgi → Yine de çalıştır** ile açabilirsin.

**Seçenek B — Kaynaktan çalıştır (geliştiriciler için)** — Python 3.10+ gerekir.

```bash
git clone https://github.com/Scainest/Teufort-Toolkit.git
cd Teufort-Toolkit
pip install -r requirements.txt
python main.py
```

### 📖 Kullanım

Uygulama açıldığında TF2 klasörünü otomatik bulur. Bulamazsa **📁 El ile Seç**
ile `...\Team Fortress 2\tf` klasörünü gösterebilirsin. Her sekmenin **Kayıt
Dizini** + **Göz At** ayarı vardır; `config.json`'a kaydedilir.

**🎨 Sprey Oluşturucu**

1. **Görsel Seç** (`.png / .jpg / .gif`) — GIF'ler animasyonlu desteklenir. İlk
   defa deniyorsan **🧪 Örnek** butonuyla gömülü örnek görseli tek tıkla yükle.
2. Sprey adını ve maks. çözünürlüğü (512/256/128) belirle.
3. **Oyun İçi (VTF)** ile spreyin oyunda gerçekte nasıl görüneceğini (DXT
   sıkıştırma dahil) gör.
4. **Kayıt Dizini** olarak `...\tf\materials\vgui\logos` seç ve **Sprey Oluştur**.
5. Oyunda: **Ayarlar → Multiplayer → Sprey** listesinden seç.

**🖼️ Objector Maker (Full-Color Conscientious Objector)**

1. **Görsel Seç**, kare kırpma alanını sürükleyip boyutlandır — çıktı ve tabela
   önizlemesi anında güncellenir.
2. **Çözünürlük**: `256 (önerilen)` / `128 (en uyumlu)` / `512 (en keskin)`.
3. **Kayıt Dizini** olarak custom klasörünü seç (örn. `...\tf\custom\BenimModum`).
   Dosya otomatik doğru yola yazılır:
   `scripts\items\custom_texture_blend_layers\paper_overlay.png`
4. **TF2'yi tamamen kapat**, dosyayı oluştur, oyunu aç ve **Decal Tool** ile
   Conscientious Objector'a `paper_overlay`'i uygula.

> ⚠️ Bu, Source motorunun asenkron doku yüklemesini kullanır ve bazen hemen
> görünmez. Görünmezse çözünürlüğü **128**'e al, GPU sürücülerini güncelle, sabit
> bir `-dxlevel` launch seçeneği ekle ve TF2'yi yeniden başlat. Not:
> `materials\...` yolu **çalışmaz** — dosya `scripts\items\...` altında olmalı.

**🔊 Hitsound Kesici**

1. **Ses Dosyası Seç** (`.mp3 / .wav / .ogg / .flac`).
2. Dalga formundaki turuncu tutamaçlarla başlangıç/bitişi seç, **▶ Önizle** ile dinle.
3. **Kayıt Dizini** olarak custom klasörünü seç.
4. **🎯 Hitsound** veya **💀 Killsound Olarak Aktar** — sırasıyla
   `sound\ui\hitsound.wav` / `sound\ui\killsound.wav` olarak kaydedilir.

> Hitsound'un çalışması için oyunda **Options → Advanced → "Play a hit sound"** açık olmalı.

### 🛠️ Kaynaktan .exe Derleme

```bash
pip install -r requirements.txt pyinstaller
python assets/make_icon.py
```

Ardından `build.bat` dosyasını çalıştır **veya** yukarıdaki (English bölümündeki)
`pyinstaller` komutunu ver. Çıktı: `dist\Teufort Toolkit.exe` (~31 MB).
- `scipy` bilerek hariç tutulur (~100 MB tasarruf); ses yeniden örnekleme
  `core/audio.py` içindeki saf-numpy pencereli-sinc filtresiyle yapılır (≈85 dB SNR).
- Frozen (exe) modda `config.json`, `%APPDATA%\TeufortToolkit\` altında tutulur.

### 🧪 Testler

```bash
python tests/test_core.py       # çekirdek doğrulama (VTF ayrıştırıcı + DXT çözücü)
python tests/test_gui_smoke.py  # üç sekmeyi uçtan uca süren GUI duman testi
```

### ❓ Sık Karşılaşılan Sorunlar

- **"TF2 bulunamadı"** → **📁 El ile Seç** ile `...\Team Fortress 2\tf` klasörünü göster.
- **Sprey oyunda görünmüyor** → Çıktının `tf\materials\vgui\logos` içinde ve oyunda
  seçili olduğundan emin ol.
- **Objector renkli çıkmıyor** → Dosya `scripts\items\custom_texture_blend_layers`
  altında olmalı; çözünürlüğü 128'e alıp tekrar dene, TF2'yi yeniden başlat.
- **MP3 açılmıyor** → Program libsndfile ile gelir; yine de sorun olursa `.wav`'a çevir.

### ⚠️ "Windows bilgisayarınızı korudu" uyarısı (SmartScreen)

İlk çalıştırmada Windows **"Bilinmeyen yayımcı"** diyebilir: **Ek bilgi → Yine de
çalıştır** ile aç. **Bu bir virüs uyarısı değildir** — ücretli bir *kod imzalama
sertifikası* ile imzalanmamış ve henüz yeterince indirilmemiş her yeni uygulamada
çıkar. Kaynak kod tamamen açık; istersen `build.bat` ile aynı exe'yi kendin
üretebilirsin. Program yalnızca senin seçtiğin klasörlere yazar; kurulum yapmaz,
internete veri göndermez.

**Antivirüs yanlış alarmı:** PyInstaller tek-dosya exe'leri bazen 1–4 sezgisel
motorda (`Riskware.PyInstaller` gibi) alarm verir çünkü kendini geçici klasöre
açar — normaldir ve zararsızdır; büyük motorlar (Microsoft Defender, Kaspersky,
BitDefender, ESET, Avast…) temizdir. Her sürümün **SHA-256** değeri kendi release
sayfasındadır; indirdiğin dosyayı `Get-FileHash "Teufort Toolkit.exe" -Algorithm
SHA256` ile doğrulayabilirsin.

Uyarıyı tamamen kaldırmak için exe'yi bir kod imzalama sertifikasıyla imzalamak
gerekir (EV sertifika = anında güven ama pahalı; Azure Trusted Signing ~aylık $10;
SignPath'in açık kaynak ücretsiz planı) ya da zamanla SmartScreen itibarının oluşması.

### 📜 Lisans

[MIT](LICENSE) — dilediğin gibi kullan, değiştir, dağıt. Bu araç hayran yapımıdır
ve Valve ile bir bağlantısı ya da onayı yoktur.
