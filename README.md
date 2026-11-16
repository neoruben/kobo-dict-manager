# Kobo DictManager

A modern, open-source desktop utility for Windows to effortlessly manage, switch, and protect custom dictionaries on Kobo eReaders.

<p align="center">
  <img src="assets/screenshot.png" alt="Kobo DictManager Screenshot" width="750" />
</p>

---

## ⚡ Quick Download (Standalone Executable)

If you just want to use the application without installing Python:

1. Download **`KoboDictManager.exe`** from the [Latest Releases](https://github.com/neoruben/kobo-dict-manager/releases).
2. Double-click the `.exe` to launch. No Python or extra dependencies required!

---

## ✨ Features

- **Automatic Kobo Detection:** Automatically scans and detects connected Kobo devices over USB (`.kobo` directory verification).
- **Language-Aware Slot Matching:** Detects your Kobo device's interface language directly from configuration (`CurrentLocale`), targeting the appropriate dictionary slot (e.g., `dicthtml.zip` for English, `dicthtml-es.zip` for Spanish, `dicthtml-fr.zip` for French, etc.).
- **Wi-Fi Overwrite Protection:** Protects active custom dictionaries from being overwritten by Kobo's background Wi-Fi sync by setting read-only file attributes.
- **Factory Integrity & Backup:** Safely backs up the genuine factory dictionary on initial connection and uses SHA-256 verification to prevent custom dictionaries from ever being mistaken for factory defaults.
- **Library Management:** Add, preview, delete, and switch between multiple custom dictionaries with duplicate detection.
- **Centralized & Persistent Storage:** User libraries, catalog entries, and backups are stored centrally in `%APPDATA%\KoboDictManager`, ensuring your dictionaries are never lost when moving or updating the `.exe`. An optional portable mode can be activated with a `portable.dat` file.
- **Smooth Visual Feedback:** Real-time progress bar when transferring dictionaries to and from the eReader.
- **Multilingual UI:** Automatically detects system language with full support for Spanish, English, Catalan, Galician, Basque, French, German, Italian, and Portuguese.
- **Modern UI:** Built with CustomTkinter with support for dark and light appearance modes.

---

## ⚠️ Language Compatibility & Testing Status

> [!WARNING]
> **Experimental Multi-language Support:**
> While **Kobo DictManager** is architected and prepared to handle dictionaries for any Kobo UI language (such as English `dicthtml.zip`, Spanish `dicthtml-es.zip`, French `dicthtml-fr.zip`, German `dicthtml-de.zip`, Italian `dicthtml-it.zip`, Portuguese `dicthtml-pt.zip`, etc.), **it has currently only been tested thoroughly with Spanish (`dicthtml-es.zip`) on Kobo Clara BW**.
>
> Support for other languages is structurally ready based on Kobo firmware conventions, but has not yet been validated with physical devices in those languages. Testing feedback, issue reports, and contributions for other languages and Kobo models are very welcome!

*(Aviso en español: Aunque la aplicación está preparada internamente para gestionar diccionarios en múltiples idiomas según la configuración del lector, por ahora solo ha sido probada exhaustivamente con diccionarios en español (`dicthtml-es.zip`) en Kobo Clara BW. La compatibilidad con otros idiomas está implementada pero no ha sido testeada en dispositivos reales).*

---

## 📋 Requirements (Running from Source)

- Windows 10 / 11
- Python 3.10 or newer

Dependencies:
- `customtkinter>=5.2.0`

---

## 🚀 Running from Source

1. **Clone the repository:**
   ```bash
   git clone https://github.com/neoruben/kobo-dict-manager.git
   cd kobo-dict-manager
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python kobo_dict_manager.py
   ```
   *Or double-click `Iniciar_KoboDictManager.bat`.*

---

## 📖 How to Use

1. Connect your Kobo eReader to your PC via USB and tap **Connect** on the device screen.
2. Launch **Kobo DictManager**. The app will detect your Kobo and display its current language slot.
3. Click **Add New Dictionary** to import a custom `.zip` or `.rar` dictionary file into your local library.
4. Select the dictionary you want and click **Load into eReader** (or **Activate on Kobo**).
5. When finished, click **Eject** or safely eject your Kobo eReader before unplugging the USB cable.

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).
