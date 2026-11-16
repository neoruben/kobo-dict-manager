# Kobo DictManager

A modern, open-source desktop utility for Windows to effortlessly manage, switch, and protect custom dictionaries on Kobo eReaders.

---

## ✨ Features

- **Automatic Kobo Detection:** Automatically scans and detects connected Kobo devices over USB (`.kobo` directory verification).
- **Language-Aware Slot Matching:** Detects your Kobo device's interface language directly from configuration (`CurrentLocale`), targeting the appropriate dictionary slot (e.g., `dicthtml.zip` for English, `dicthtml-es.zip` for Spanish, `dicthtml-fr.zip` for French, etc.).
- **Wi-Fi Overwrite Protection:** Protects active custom dictionaries from being overwritten by Kobo's background Wi-Fi sync by setting read-only file attributes.
- **Safe Backup & Restore:** Automatically creates a backup of the original official dictionary upon first connection, enabling one-click restoration anytime.
- **Library Management:** Add, preview, delete, and switch between multiple custom dictionaries.
- **Integrity & Duplicate Prevention:** Uses SHA-256 checksums to verify active status and avoid duplicate imports.
- **Progress Bar & Visual Feedback:** Smooth visual cues when importing large dictionary files.
- **Multilingual UI:** Automatically detects system language with full support for Spanish, English, Catalan, Galician, Basque, French, German, Italian, and Portuguese.
- **Modern UI:** Built with CustomTkinter with support for dark and light appearance modes.

---

## 📋 Requirements

- Windows 10 / 11
- Python 3.10 or newer

Dependencies:
- `customtkinter>=5.2.0`

---

## 🚀 Quick Start

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
   *Or simply double-click `Iniciar_KoboDictManager.bat`.*

---

## 📖 How to Use

1. Connect your Kobo eReader to your PC via USB and tap **Connect** on the device screen.
2. Launch **Kobo DictManager**. The app will detect your Kobo and display its current language slot.
3. Click **Add New Dictionary** to import a custom `.zip` dictionary file into your local library.
4. Select the dictionary you want and click **Activate on Kobo**.
5. When finished, safely eject your Kobo eReader before unplugging the USB cable.

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).
