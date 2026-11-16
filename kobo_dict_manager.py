"""
Kobo Dictionary Manager - Aplicación de escritorio para Windows
Gestor inteligente y multi-idioma de diccionarios para ereaders Kobo.
Detecta automáticamente el idioma configurado en el propio lector Kobo
(CurrentLocale en Kobo eReader.conf), adaptando los slots correspondientes
(dicthtml.zip para inglés, dicthtml-es.zip para español, dicthtml-fr.zip para francés, etc.),
asignando la extensión correcta a cada archivo y previniendo la sobreescritura por Wi-Fi.
"""

import os
import sys
import time
import json
import shutil
import hashlib
import tempfile
import threading
import subprocess
import zipfile
import ctypes
import locale
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

# Configuración visual
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

def get_data_dir():
    """
    Retorna el directorio central de datos del usuario (%APPDATA%/KoboDictManager).
    Permite modo portable si existe un archivo 'portable.dat' en la carpeta del ejecutable/script.
    """
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(exe_dir, "portable.dat")):
        return exe_dir

    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")
    data_dir = os.path.join(appdata, "KoboDictManager")
    os.makedirs(data_dir, exist_ok=True)

    # Migración automática si existen archivos en carpetas locales previas
    legacy_lib = os.path.join(exe_dir, "library")
    legacy_backups = os.path.join(exe_dir, "backups")
    target_lib = os.path.join(data_dir, "library")
    target_backups = os.path.join(data_dir, "backups")
    os.makedirs(target_lib, exist_ok=True)
    os.makedirs(target_backups, exist_ok=True)

    if os.path.exists(legacy_lib) and os.path.abspath(legacy_lib) != os.path.abspath(target_lib):
        for f in os.listdir(legacy_lib):
            src = os.path.join(legacy_lib, f)
            dst = os.path.join(target_lib, f)
            if not os.path.exists(dst) and os.path.isfile(src):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass

    if os.path.exists(legacy_backups) and os.path.abspath(legacy_backups) != os.path.abspath(target_backups):
        for f in os.listdir(legacy_backups):
            src = os.path.join(legacy_backups, f)
            dst = os.path.join(target_backups, f)
            if not os.path.exists(dst) and os.path.isfile(src):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass

    return data_dir

DATA_DIR = get_data_dir()
LIBRARY_DIR = os.path.join(DATA_DIR, "library")
BACKUPS_DIR = os.path.join(DATA_DIR, "backups")
CATALOG_FILE = os.path.join(LIBRARY_DIR, "catalog.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"

os.makedirs(LIBRARY_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

# Especificaciones oficiales de fábrica de Kobo para slots conocidos
OFFICIAL_FACTORY_SPECS = {
    "dicthtml-es.zip": {
        "sha256": "54660219f6912c8e8234193c4d90846ca8d7750f5a180287ef49ba572356c84d",
        "size": 13976932
    }
}

# Idiomas soportados por la interfaz de usuario
SUPPORTED_LANGUAGES = {
    "es": "Español",
    "en": "English",
    "ca": "Català",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Português",
}

# Mapeo de slots de idioma en Kobo
LANGUAGE_SLOT_INFO = {
    "en": {"slot": "dicthtml.zip", "name": "English"},
    "es": {"slot": "dicthtml-es.zip", "name": "Español"},
    "fr": {"slot": "dicthtml-fr.zip", "name": "Français"},
    "de": {"slot": "dicthtml-de.zip", "name": "Deutsch"},
    "it": {"slot": "dicthtml-it.zip", "name": "Italiano"},
    "pt": {"slot": "dicthtml-pt.zip", "name": "Português"},
    "nl": {"slot": "dicthtml-nl.zip", "name": "Nederlands"},
    "ca": {"slot": "dicthtml-ca.zip", "name": "Català"},
}

TRANSLATIONS = {
    "es": {
        "app_title": "Kobo DictManager - Gestor de Diccionarios",
        "searching": "⏳ Buscando lector Kobo...",
        "connected": "🟢 Conectado: {model} ({drive}) • Idioma Kobo: {kobo_lang}",
        "waiting_usb": "🟠 Esperando conexión USB...",
        "connect_prompt": "Conecta el cable USB y pulsa 'Conectar' en la pantalla del lector.",
        "device_info": "Firmware: {fw} | Serie: {serial}...",
        "add_dicts_btn": "➕ Añadir nuevos diccionarios",
        "eject_btn": "⏏️ Expulsar",
        "ereader_dicts_title": "📖 Diccionarios del eReader ({slot_desc})",
        "factory_badge": "🏛️ PREDETERMINADO DE FÁBRICA",
        "active_badge": "✅ CARGADO EN EL EREADER (ACTIVO)",
        "protected_badge": "🔒 Protegido contra Wi-Fi Sync",
        "unprotected_badge": "⚠️ No protegido",
        "official_dict_name": "Diccionario Oficial Kobo ({lang})",
        "official_dict_desc": "Diccionario predeterminado de fábrica del eReader ({slot}). Siempre puedes volver a él.",
        "size_label": "Tamaño: {size}",
        "target_slot_label": "Destino en Kobo: {slot}",
        "file_added_label": "Archivo: {file} • Añadido: {date}",
        "currently_active_btn": "✔ Actualmente Activo",
        "load_btn": "⚡ Cargar en el eReader",
        "restore_official_btn": "⚡ Volver al Oficial de Fábrica",
        "open_folder_btn": "📁 Ver carpeta en el Kobo (.kobo/dict)",
        "ready_status": "Listo. Conecta tu lector Kobo por USB.",
        "device_ready_status": "Dispositivo {model} ({kobo_lang}) conectado en {drive}.",
        "confirm_load_title": "Confirmar carga de diccionario",
        "confirm_load_msg": "¿Deseas cargar '{name}' en tu {model} (Slot: {slot})?\n\n• Se guardará una copia de seguridad del diccionario que tienes ahora.\n• Se activará automáticamente la protección contra sobrescritura por Wi-Fi.",
        "confirm_restore_title": "Volver al diccionario oficial",
        "confirm_restore_msg": "¿Deseas restaurar el Diccionario Oficial de fábrica ({slot}) en tu Kobo?",
        "confirm_delete_title": "Eliminar diccionario",
        "confirm_delete_msg": "¿Deseas eliminar '{name}' de tu lista de diccionarios?\n\n(El archivo original que descargaste no se borrará).",
        "uploading_title": "Subiendo al eReader...",
        "importing_title": "Importando Diccionarios...",
        "keep_usb_warning": "⚠️ Mantén el cable USB conectado hasta finalizar.",
        "copying_status": "Copiando al eReader ({slot}): {pct}% ({copied:.1f} MB de {total:.1f} MB)...",
        "load_success_title": "Diccionario Cargado",
        "load_success_msg": "El diccionario '{name}' se ha transferido e instalado con éxito como {slot} en tu Kobo.\n\n✓ El archivo está bloqueado en 'Solo lectura' para protegerlo de la sincronización Wi-Fi.\n✓ Ya puedes consultar palabras con este diccionario en tus libros.",
        "restore_success_title": "Diccionario Oficial Activo",
        "restore_success_msg": "Se ha cargado de nuevo el diccionario oficial de fábrica ({slot}) en tu Kobo.",
        "added_success_title": "Diccionarios Añadidos",
        "added_success_msg": "Se han añadido {count} diccionario(s) a tu lista:\n\n• {list}",
        "eject_confirm_title": "Expulsar Lector Kobo",
        "eject_confirm_msg": "¿Deseas expulsar con seguridad el {model} ({drive}) para desconectarlo?",
        "eject_success_title": "Dispositivo Expulsado",
        "eject_success_msg": "Ya es seguro desconectar tu {model} del ordenador.\n\n¡Feliz lectura!",
        "eject_warning_msg": "Windows ha recibido la orden de expulsión. Asegúrate de cerrar carpetas abiertas antes de retirar el cable.",
        "select_dicts_dialog_title": "Seleccionar diccionarios para añadir",
        "filetypes_desc": "Archivos de diccionario Kobo (.zip, .rar)",
        "not_connected_warning": "Conecta tu Kobo al ordenador por USB y pulsa 'Conectar' en la pantalla del lector antes de realizar esta acción.",
        "dict_already_in_library_title": "Diccionario ya cargado",
        "dict_already_in_library_msg": "El diccionario '{file}' ya está cargado en tu lista como '{name}'.\n\nNo es necesario volver a añadirlo.",
        "dict_already_active_title": "Diccionario ya activo",
        "dict_already_active_msg": "El diccionario '{name}' ya está instalado y activo actualmente en tu lector Kobo."
    },
    "en": {
        "app_title": "Kobo DictManager - Dictionary Manager",
        "searching": "⏳ Searching for Kobo reader...",
        "connected": "🟢 Connected: {model} ({drive}) • Kobo Language: {kobo_lang}",
        "waiting_usb": "🟠 Waiting for USB connection...",
        "connect_prompt": "Connect the USB cable and tap 'Connect' on the reader screen.",
        "device_info": "Firmware: {fw} | Serial: {serial}...",
        "add_dicts_btn": "➕ Add new dictionaries",
        "eject_btn": "⏏️ Eject",
        "ereader_dicts_title": "📖 eReader Dictionaries ({slot_desc})",
        "factory_badge": "🏛️ FACTORY DEFAULT",
        "active_badge": "✅ LOADED IN EREADER (ACTIVE)",
        "protected_badge": "🔒 Protected from Wi-Fi Sync",
        "unprotected_badge": "⚠️ Unprotected",
        "official_dict_name": "Official Kobo Dictionary ({lang})",
        "official_dict_desc": "eReader factory default dictionary ({slot}). You can always switch back to it.",
        "size_label": "Size: {size}",
        "target_slot_label": "Target in Kobo: {slot}",
        "file_added_label": "File: {file} • Added: {date}",
        "currently_active_btn": "✔ Currently Active",
        "load_btn": "⚡ Load into eReader",
        "restore_official_btn": "⚡ Restore Factory Default",
        "open_folder_btn": "📁 Open Kobo folder (.kobo/dict)",
        "ready_status": "Ready. Connect your Kobo reader via USB.",
        "device_ready_status": "Device {model} ({kobo_lang}) connected on {drive}.",
        "confirm_load_title": "Confirm dictionary load",
        "confirm_load_msg": "Do you want to load '{name}' onto your {model} (Slot: {slot})?\n\n• A backup of your current dictionary will be saved.\n• Protection against Wi-Fi sync overwrite will be enabled automatically.",
        "confirm_restore_title": "Restore factory default dictionary",
        "confirm_restore_msg": "Do you want to restore the official factory dictionary ({slot}) on your Kobo?",
        "confirm_delete_title": "Delete dictionary",
        "confirm_delete_msg": "Do you want to delete '{name}' from your dictionary list?\n\n(The original file on your computer will not be deleted).",
        "uploading_title": "Uploading to eReader...",
        "importing_title": "Importing Dictionaries...",
        "keep_usb_warning": "⚠️ Keep the USB cable connected until finished.",
        "copying_status": "Copying to eReader ({slot}): {pct}% ({copied:.1f} MB of {total:.1f} MB)...",
        "load_success_title": "Dictionary Loaded",
        "load_success_msg": "The dictionary '{name}' has been successfully transferred and installed as {slot} on your Kobo.\n\n✓ The file is locked as 'Read-Only' to protect it from Wi-Fi sync.\n✓ You can now look up words in your books with this dictionary.",
        "restore_success_title": "Official Dictionary Active",
        "restore_success_msg": "The official factory dictionary ({slot}) has been restored on your Kobo.",
        "added_success_title": "Dictionaries Added",
        "added_success_msg": "Added {count} dictionary/dictionaries to your list:\n\n• {list}",
        "eject_confirm_title": "Eject Kobo Reader",
        "eject_confirm_msg": "Do you want to safely eject {model} ({drive}) to disconnect it?",
        "eject_success_title": "Device Ejected",
        "eject_success_msg": "It is now safe to disconnect your {model} from your computer.\n\nHappy reading!",
        "eject_warning_msg": "Windows has received the ejection command. Please make sure any open folders are closed before unplugging.",
        "select_dicts_dialog_title": "Select dictionaries to add",
        "filetypes_desc": "Kobo dictionary files (.zip, .rar)",
        "not_connected_warning": "Connect your Kobo to the computer via USB and tap 'Connect' on the screen before performing this action.",
        "dict_already_in_library_title": "Dictionary already loaded",
        "dict_already_in_library_msg": "The dictionary '{file}' is already loaded in your list as '{name}'.\n\nNo need to add it again.",
        "dict_already_active_title": "Dictionary already active",
        "dict_already_active_msg": "The dictionary '{name}' is already installed and active on your Kobo reader."
    },
    "ca": {
        "app_title": "Kobo DictManager - Gestor de Diccionaris",
        "searching": "⏳ Cercant lector Kobo...",
        "connected": "🟢 Connectat: {model} ({drive}) • Idioma Kobo: {kobo_lang}",
        "waiting_usb": "🟠 Esperant connexió USB...",
        "connect_prompt": "Connecta el cable USB i prem 'Connectar' a la pantalla del lector.",
        "device_info": "Firmware: {fw} | Sèrie: {serial}...",
        "add_dicts_btn": "➕ Afegir nous diccionaris",
        "eject_btn": "⏏️ Expulsar",
        "ereader_dicts_title": "📖 Diccionaris de l'eReader ({slot_desc})",
        "factory_badge": "🏛️ PREDETERMINAT DE FÀBRICA",
        "active_badge": "✅ CARREGAT A L'EREADER (ACTIU)",
        "protected_badge": "🔒 Protegit contra Wi-Fi Sync",
        "unprotected_badge": "⚠️ No protegit",
        "official_dict_name": "Diccionari Oficial Kobo ({lang})",
        "official_dict_desc": "Diccionari predeterminat de fàbrica de l'eReader ({slot}). Sempre pots tornar-hi.",
        "size_label": "Mida: {size}",
        "target_slot_label": "Destinació a Kobo: {slot}",
        "file_added_label": "Fitxer: {file} • Afegit: {date}",
        "currently_active_btn": "✔ Actualment Actiu",
        "load_btn": "⚡ Carregar a l'eReader",
        "restore_official_btn": "⚡ Tornar a l'Oficial de Fàbrica",
        "open_folder_btn": "📁 Veure carpeta al Kobo (.kobo/dict)",
        "ready_status": "Llest. Connecta el teu lector Kobo per USB.",
        "device_ready_status": "Dispositiu {model} ({kobo_lang}) connectat a {drive}.",
        "confirm_load_title": "Confirmar càrrega de diccionari",
        "confirm_load_msg": "Vols carregar '{name}' al teu {model} (Slot: {slot})?\n\n• Es desarà una còpia de seguretat del diccionari actual.\n• S'activarà automàticament la protecció contra sobreescriptura per Wi-Fi.",
        "confirm_restore_title": "Tornar al diccionari oficial",
        "confirm_restore_msg": "Vols restaurar el Diccionari Oficial de fàbrica ({slot}) al teu Kobo?",
        "confirm_delete_title": "Eliminar diccionari",
        "confirm_delete_msg": "Vols eliminar '{name}' de la teva llista de diccionaris?\n\n(El fitxer original no s'eliminarà).",
        "uploading_title": "Pujant a l'eReader...",
        "importing_title": "Important Diccionaris...",
        "keep_usb_warning": "⚠️ Mantén el cable USB connectat fins que finalitzi.",
        "copying_status": "Copiant a l'eReader ({slot}): {pct}% ({copied:.1f} MB de {total:.1f} MB)...",
        "load_success_title": "Diccionari Carregat",
        "load_success_msg": "El diccionari '{name}' s'ha transferit i instal·lat amb èxit com {slot} al teu Kobo.\n\n✓ El fitxer està protegit en 'Només lectura' per evitar la sincronització Wi-Fi.",
        "restore_success_title": "Diccionari Oficial Actiu",
        "restore_success_msg": "S'ha restaurat el diccionari oficial de fàbrica ({slot}) al teu Kobo.",
        "added_success_title": "Diccionaris Afegits",
        "added_success_msg": "S'han afegit {count} diccionari(s) a la teva llista:\n\n• {list}",
        "eject_confirm_title": "Expulsar Lector Kobo",
        "eject_confirm_msg": "Vols expulsar amb seguretat el {model} ({drive}) per desconnectar-lo?",
        "eject_success_title": "Dispositiu Expulsat",
        "eject_success_msg": "Ja és segur desconnectar el teu {model} de l'ordinador.\n\nBona lectura!",
        "eject_warning_msg": "Windows ha rebut l'ordre d'expulsió. Tanca les carpetes obertes abans de retirar el cable.",
        "select_dicts_dialog_title": "Seleccionar diccionaris per afegir",
        "filetypes_desc": "Fitxers de diccionari Kobo (.zip, .rar)",
        "not_connected_warning": "Connecta el teu Kobo per USB i prem 'Connectar' a la pantalla abans de fer aquesta acció."
    },
    "fr": {
        "app_title": "Kobo DictManager - Gestionnaire de Dictionnaires",
        "searching": "⏳ Recherche du lecteur Kobo...",
        "connected": "🟢 Connecté: {model} ({drive}) • Langue Kobo: {kobo_lang}",
        "waiting_usb": "🟠 En attente de connexion USB...",
        "connect_prompt": "Branchez le câble USB et appuyez sur 'Connecter' sur l'écran.",
        "device_info": "Firmware: {fw} | Série: {serial}...",
        "add_dicts_btn": "➕ Ajouter de nouveaux dictionnaires",
        "eject_btn": "⏏️ Éjecter",
        "ereader_dicts_title": "📖 Dictionnaires de la liseuse ({slot_desc})",
        "factory_badge": "🏛️ DÉFAUT D'USINE",
        "active_badge": "✅ CHARGÉ DANS LA LISEUSE (ACTIF)",
        "protected_badge": "🔒 Protégé contre Wi-Fi Sync",
        "unprotected_badge": "⚠️ Non protégé",
        "official_dict_name": "Dictionnaire Officiel Kobo ({lang})",
        "official_dict_desc": "Dictionnaire d'usine de la liseuse ({slot}). Vous pouvez toujours y revenir.",
        "size_label": "Taille: {size}",
        "target_slot_label": "Cible sur Kobo: {slot}",
        "file_added_label": "Fichier: {file} • Ajouté: {date}",
        "currently_active_btn": "✔ Actuellement Actif",
        "load_btn": "⚡ Charger dans la liseuse",
        "restore_official_btn": "⚡ Rétablir le défaut d'usine",
        "open_folder_btn": "📁 Voir le dossier Kobo (.kobo/dict)",
        "ready_status": "Prêt. Connectez votre liseuse Kobo par USB.",
        "device_ready_status": "Appareil {model} ({kobo_lang}) connecté sur {drive}.",
        "confirm_load_title": "Confirmer le chargement du dictionnaire",
        "confirm_load_msg": "Voulez-vous charger '{name}' sur votre {model} (Slot: {slot}) ?\n\n• Une sauvegarde sera effectuée.\n• La protection contre le Wi-Fi sera activée.",
        "confirm_restore_title": "Rétablir le dictionnaire d'usine",
        "confirm_restore_msg": "Voulez-vous rétablir le dictionnaire officiel d'usine ({slot}) sur votre Kobo ?",
        "confirm_delete_title": "Supprimer le dictionnaire",
        "confirm_delete_msg": "Voulez-vous supprimer '{name}' de votre liste ?\n\n(Le fichier original ne sera pas supprimé).",
        "uploading_title": "Transfert vers la liseuse...",
        "importing_title": "Importation des dictionnaires...",
        "keep_usb_warning": "⚠️ Maintenez le câble USB branché jusqu'à la fin.",
        "copying_status": "Copie vers la liseuse ({slot}): {pct}% ({copied:.1f} Mo sur {total:.1f} Mo)...",
        "load_success_title": "Dictionnaire Chargé",
        "load_success_msg": "Le dictionnaire '{name}' a été installé avec succès comme {slot}.\n\n✓ Le fichier est en lecture seule pour éviter tout écrasement par Wi-Fi.",
        "restore_success_title": "Dictionnaire Officiel Actif",
        "restore_success_msg": "Le dictionnaire officiel d'usine ({slot}) a été restauré.",
        "added_success_title": "Dictionnaires Ajoutés",
        "added_success_msg": "{count} dictionnaire(s) ajouté(s) à votre liste :\n\n• {list}",
        "eject_confirm_title": "Éjecter la liseuse Kobo",
        "eject_confirm_msg": "Voulez-vous éjecter {model} ({drive}) en toute sécurité ?",
        "eject_success_title": "Appareil Éjecté",
        "eject_success_msg": "Vous pouvez maintenant débrancher votre {model}.\n\nBonne lecture !",
        "eject_warning_msg": "Commande d'éjection envoyée. Fermez tout dossier ouvert avant de débrancher.",
        "select_dicts_dialog_title": "Sélectionner des dictionnaires à ajouter",
        "filetypes_desc": "Fichiers de dictionnaire Kobo (.zip, .rar)",
        "not_connected_warning": "Connectez votre Kobo par USB et appuyez sur 'Connecter' avant d'effectuer cette action."
    },
    "de": {
        "app_title": "Kobo DictManager - Wörterbuch-Manager",
        "searching": "⏳ Kobo-Reader wird gesucht...",
        "connected": "🟢 Verbunden: {model} ({drive}) • Kobo-Sprache: {kobo_lang}",
        "waiting_usb": "🟠 Warte auf USB-Verbindung...",
        "connect_prompt": "USB-Kabel anschließen und auf dem Reader 'Verbinden' wählen.",
        "device_info": "Firmware: {fw} | Serie: {serial}...",
        "add_dicts_btn": "➕ Neue Wörterbücher hinzufügen",
        "eject_btn": "⏏️ Auswerfen",
        "ereader_dicts_title": "📖 eReader-Wörterbücher ({slot_desc})",
        "factory_badge": "🏛️ WERKSEINSTELLUNG",
        "active_badge": "✅ GELADEN IM EREADER (AKTIV)",
        "protected_badge": "🔒 Vor Wi-Fi-Sync geschützt",
        "unprotected_badge": "⚠️ Nicht geschützt",
        "official_dict_name": "Offizielles Kobo-Wörterbuch ({lang})",
        "official_dict_desc": "Standard-Werks-Wörterbuch des eReaders ({slot}). Sie können jederzeit zurückkehren.",
        "size_label": "Größe: {size}",
        "target_slot_label": "Ziel in Kobo: {slot}",
        "file_added_label": "Datei: {file} • Hinzugefügt: {date}",
        "currently_active_btn": "✔ Derzeit Aktiv",
        "load_btn": "⚡ In eReader laden",
        "restore_official_btn": "⚡ Werkseinstellung wiederherstellen",
        "open_folder_btn": "📁 Kobo-Ordner öffnen (.kobo/dict)",
        "ready_status": "Bereit. Schließen Sie Ihren Kobo per USB an.",
        "device_ready_status": "Gerät {model} ({kobo_lang}) verbunden auf {drive}.",
        "confirm_load_title": "Wörterbuch-Laden bestätigen",
        "confirm_load_msg": "Möchten Sie '{name}' auf Ihren {model} (Slot: {slot}) laden?\n\n• Ein Backup des aktuellen Wörterbuchs wird gespeichert.\n• Schutz vor Wi-Fi-Überschreibung wird aktiviert.",
        "confirm_restore_title": "Werkseinstellung wiederherstellen",
        "confirm_restore_msg": "Möchten Sie das offizielle Werks-Wörterbuch ({slot}) wiederherstellen?",
        "confirm_delete_title": "Wörterbuch löschen",
        "confirm_delete_msg": "Möchten Sie '{name}' aus der Liste löschen?\n\n(Die Originaldatei wird nicht gelöscht).",
        "uploading_title": "Wird auf eReader übertragen...",
        "importing_title": "Wörterbücher werden importiert...",
        "keep_usb_warning": "⚠️ Bitte USB-Kabel bis zum Abschluss eingesteckt lassen.",
        "copying_status": "Kopieren zum eReader ({slot}): {pct}% ({copied:.1f} MB von {total:.1f} MB)...",
        "load_success_title": "Wörterbuch Geladen",
        "load_success_msg": "Das Wörterbuch '{name}' wurde erfolgreich als {slot} übertragen.\n\n✓ Die Datei ist schreibgeschützt gegen Wi-Fi-Sync.",
        "restore_success_title": "Offizielles Wörterbuch Aktiv",
        "restore_success_msg": "Das offizielle Werks-Wörterbuch ({slot}) wurde wiederhergestellt.",
        "added_success_title": "Wörterbücher Hinzugefügt",
        "added_success_msg": "{count} Wörterbuch/Wörterbücher hinzugefügt:\n\n• {list}",
        "eject_confirm_title": "Kobo-Reader auswerfen",
        "eject_confirm_msg": "Möchten Sie {model} ({drive}) sicher auswerfen?",
        "eject_success_title": "Gerät Ausgeworfen",
        "eject_success_msg": "Sie können Ihren {model} jetzt sicher abziehen.\n\nViel Spaß beim Lesen!",
        "eject_warning_msg": "Auswurfbefehl gesendet. Bitte Ordner vor dem Trennen schließen.",
        "select_dicts_dialog_title": "Wörterbücher zum Hinzufügen auswählen",
        "filetypes_desc": "Kobo-Wörterbuchdateien (.zip, .rar)",
        "not_connected_warning": "Schließen Sie Ihren Kobo per USB an und tippen Sie auf 'Verbinden'."
    },
    "it": {
        "app_title": "Kobo DictManager - Gestore di Dizionari",
        "searching": "⏳ Ricerca lettore Kobo...",
        "connected": "🟢 Connesso: {model} ({drive}) • Lingua Kobo: {kobo_lang}",
        "waiting_usb": "🟠 In attesa di connessione USB...",
        "connect_prompt": "Collega il cavo USB e tocca 'Connetti' sullo schermo del lettore.",
        "device_info": "Firmware: {fw} | Serie: {serial}...",
        "add_dicts_btn": "➕ Aggiungi nuovi dizionari",
        "eject_btn": "⏏️ Espelli",
        "ereader_dicts_title": "📖 Dizionari dell'eReader ({slot_desc})",
        "factory_badge": "🏛️ PREDEFINITO DI FABBRICA",
        "active_badge": "✅ CARICATO SULL'EREADER (ATTIVO)",
        "protected_badge": "🔒 Protetto da Wi-Fi Sync",
        "unprotected_badge": "⚠️ Non protetto",
        "official_dict_name": "Dizionario Ufficiale Kobo ({lang})",
        "official_dict_desc": "Dizionario predefinito di fabbrica dell'eReader ({slot}). Puoi sempre ripristinarlo.",
        "size_label": "Dimensione: {size}",
        "target_slot_label": "Destinazione su Kobo: {slot}",
        "file_added_label": "File: {file} • Aggiunto: {date}",
        "currently_active_btn": "✔ Attualmente Attivo",
        "load_btn": "⚡ Carica nell'eReader",
        "restore_official_btn": "⚡ Ripristina predefinito di fabbrica",
        "open_folder_btn": "📁 Apri cartella sul Kobo (.kobo/dict)",
        "ready_status": "Pronto. Collega il tuo lettore Kobo via USB.",
        "device_ready_status": "Dispositivo {model} ({kobo_lang}) connesso su {drive}.",
        "confirm_load_title": "Conferma caricamento dizionario",
        "confirm_load_msg": "Vuoi caricare '{name}' sul tuo {model} (Slot: {slot})?\n\n• Verrà eseguito un backup.\n• La protezione da sovrascrittura Wi-Fi verrà attivata.",
        "confirm_restore_title": "Ripristina dizionario ufficiale",
        "confirm_restore_msg": "Vuoi ripristinare il dizionario ufficiale di fabbrica ({slot}) sul tuo Kobo?",
        "confirm_delete_title": "Elimina dizionario",
        "confirm_delete_msg": "Vuoi eliminare '{name}' dall'elenco?\n\n(Il file originale non verrà eliminato).",
        "uploading_title": "Caricamento sull'eReader...",
        "importing_title": "Importazione dizionari...",
        "keep_usb_warning": "⚠️ Mantieni il cavo USB collegato fino al termine.",
        "copying_status": "Copia sull'eReader ({slot}): {pct}% ({copied:.1f} MB su {total:.1f} MB)...",
        "load_success_title": "Dizionario Caricato",
        "load_success_msg": "Il dizionario '{name}' è stato installato come {slot} sul tuo Kobo.\n\n✓ Il file è in sola lettura per proteggerlo da Wi-Fi sync.",
        "restore_success_title": "Dizionario Ufficiale Attivo",
        "restore_success_msg": "Il dizionario ufficiale di fabbrica ({slot}) è stato ripristinato.",
        "added_success_title": "Dizionari Aggiunti",
        "added_success_msg": "Aggiunti {count} dizionario/i alla lista:\n\n• {list}",
        "eject_confirm_title": "Espelli lettore Kobo",
        "eject_confirm_msg": "Vuoi espellere in sicurezza {model} ({drive})?",
        "eject_success_title": "Dispositivo Espulso",
        "eject_success_msg": "Ora puoi scollegare in sicurezza il tuo {model}.\n\nBuona lettura!",
        "eject_warning_msg": "Comando di espulsione inviato. Chiudi le cartelle aperte prima di scollegare.",
        "select_dicts_dialog_title": "Seleziona dizionari da aggiungere",
        "filetypes_desc": "File dizionario Kobo (.zip, .rar)",
        "not_connected_warning": "Collega il Kobo via USB e tocca 'Connetti' prima di procedere."
    },
    "pt": {
        "app_title": "Kobo DictManager - Gestor de Dicionários",
        "searching": "⏳ Procurando leitor Kobo...",
        "connected": "🟢 Conectado: {model} ({drive}) • Idioma Kobo: {kobo_lang}",
        "waiting_usb": "🟠 Aguardando conexão USB...",
        "connect_prompt": "Conecte o cabo USB e toque em 'Conectar' na tela do leitor.",
        "device_info": "Firmware: {fw} | Série: {serial}...",
        "add_dicts_btn": "➕ Adicionar novos dicionários",
        "eject_btn": "⏏️ Ejetar",
        "ereader_dicts_title": "📖 Dicionários do eReader ({slot_desc})",
        "factory_badge": "🏛️ PADRÃO DE FÁBRICA",
        "active_badge": "✅ CARREGADO NO EREADER (ATIVO)",
        "protected_badge": "🔒 Protegido contra Wi-Fi Sync",
        "unprotected_badge": "⚠️ Não protegido",
        "official_dict_name": "Dicionário Oficial Kobo ({lang})",
        "official_dict_desc": "Dicionário padrão de fábrica do eReader ({slot}). Você sempre pode voltar para ele.",
        "size_label": "Tamanho: {size}",
        "target_slot_label": "Destino no Kobo: {slot}",
        "file_added_label": "Arquivo: {file} • Adicionado: {date}",
        "currently_active_btn": "✔ Atualmente Ativo",
        "load_btn": "⚡ Carregar no eReader",
        "restore_official_btn": "⚡ Voltar ao Padrão de Fábrica",
        "open_folder_btn": "📁 Ver pasta no Kobo (.kobo/dict)",
        "ready_status": "Pronto. Conecte seu leitor Kobo via USB.",
        "device_ready_status": "Dispositivo {model} ({kobo_lang}) conectado em {drive}.",
        "confirm_load_title": "Confirmar carregamento do dicionário",
        "confirm_load_msg": "Deseja carregar '{name}' no seu {model} (Slot: {slot})?\n\n• Uma cópia de segurança será criada.\n• A proteção contra Wi-Fi será ativada automaticamente.",
        "confirm_restore_title": "Restaurar dicionário oficial",
        "confirm_restore_msg": "Deseja restaurar o dicionário oficial de fábrica ({slot}) no seu Kobo?",
        "confirm_delete_title": "Excluir dicionário",
        "confirm_delete_msg": "Deseja excluir '{name}' da sua lista de dicionários?\n\n(O arquivo original não será excluído).",
        "uploading_title": "Transferindo para o eReader...",
        "importing_title": "Importando dicionários...",
        "keep_usb_warning": "⚠️ Mantenha o cabo USB conectado até finalizar.",
        "copying_status": "Copiando para o eReader ({slot}): {pct}% ({copied:.1f} MB de {total:.1f} MB)...",
        "load_success_title": "Dicionário Carregado",
        "load_success_msg": "O dicionário '{name}' foi instalado como {slot} no seu Kobo.\n\n✓ O arquivo está protegido como 'Somente leitura' contra Wi-Fi sync.",
        "restore_success_title": "Dicionário Oficial Ativo",
        "restore_success_msg": "O dicionário oficial de fábrica ({slot}) foi restaurado.",
        "added_success_title": "Dicionários Adicionados",
        "added_success_msg": "Adicionado(s) {count} dicionário(s) à sua lista:\n\n• {list}",
        "eject_confirm_title": "Ejetar leitor Kobo",
        "eject_confirm_msg": "Deseja ejetar com segurança o {model} ({drive})?",
        "eject_success_title": "Dispositivo Ejetado",
        "eject_success_msg": "Agora é seguro desconectar seu {model}.\n\nBoa leitura!",
        "eject_warning_msg": "Comando de ejeção enviado. Feche pastas abertas antes de desconectar.",
        "select_dicts_dialog_title": "Selecionar dicionários para adicionar",
        "filetypes_desc": "Arquivos de dicionário Kobo (.zip, .rar)",
        "not_connected_warning": "Conecte o Kobo via USB e toque em 'Conectar' antes de prosseguir."
    }
}


def detect_system_language():
    """Detecta el idioma del sistema con fallback a 'en'."""
    code = "en"
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        loc = locale.windows_locale.get(lang_id, "")
        if loc:
            code = loc.split("_")[0].lower()
    except Exception:
        try:
            loc = locale.getlocale()[0]
            if loc:
                code = loc.split("_")[0].lower()
        except Exception:
            code = "en"

    if code in SUPPORTED_LANGUAGES:
        return code
    return "en"


def load_saved_language():
    """Carga el idioma guardado o detecta el del sistema."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lang = data.get("language")
                if lang in SUPPORTED_LANGUAGES:
                    return lang
        except Exception:
            pass
    return detect_system_language()


def save_language_preference(lang_code):
    """Guarda la preferencia de idioma del usuario."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"language": lang_code}, f, indent=2)
    except Exception as e:
        print(f"Error guardando idioma: {e}")


def detect_target_slot_for_filename(filename, default_slot="dicthtml-es.zip"):
    """
    Determina la ranura de destino:
    - Si el archivo ya tiene el nombre nativo de Kobo (ej. dicthtml.zip o dicthtml-xx.zip), lo respeta.
    - En caso contrario, se le asigna directamente el slot principal del idioma del Kobo del usuario.
    """
    nl = filename.lower()
    if nl.startswith("dicthtml") and nl.endswith(".zip"):
        return nl
    return default_slot


KOBO_MODELS = {
    "391": "Kobo Clara BW",
    "390": "Kobo Clara Colour",
    "393": "Kobo Libra Colour",
    "388": "Kobo Elipsa 2E",
    "387": "Kobo Clara 2E",
    "384": "Kobo Sage",
    "381": "Kobo Libra 2",
    "386": "Kobo Elipsa",
    "382": "Kobo Nia",
    "380": "Kobo Libra H2O",
    "378": "Kobo Forma",
    "376": "Kobo Clara HD",
    "374": "Kobo Aura ONE",
    "375": "Kobo Aura Edition 2",
    "373": "Kobo Aura H2O Edition 2",
    "370": "Kobo Touch 2.0",
    "360": "Kobo Glo HD",
    "350": "Kobo Aura H2O",
    "340": "Kobo Aura",
    "330": "Kobo Glo",
    "320": "Kobo Mini",
    "310": "Kobo Touch",
    "N365": "Kobo Clara BW",
    "N367": "Kobo Clara Colour",
    "N428": "Kobo Clara 2E",
    "N306": "Kobo Clara HD",
    "N418": "Kobo Libra 2",
    "N873": "Kobo Libra H2O",
    "N778": "Kobo Forma",
}

KNOWN_HASHES = {
    "54660219f6912c8e8234193c4d90846ca8d7750f5a180287ef49ba572356c84d": "Oficial Rakuten Kobo (Español)",
    "930d927d4103fb8a1555e73db5f32ffa9204f62e87528ea8cf31515502e9b049": "DRAE con Inflexiones (Negatus)",
    "cd381cdf6f8072b6a94e0be67eb2fa38fee23b2474695a46626ffe93bfc50da2": "DRAE (jpalacios)",
    "07d238ee0edcf3938238688f3911949db51765af49330f21861797308fdea27c": "DRAE (Tokland4)",
    "8c6ae5b5e84c33a5fdd7845cf3659f54d3d9dc7cd2af25e01875729204d32c17": "miniDRAE (Norishen4)",
}


def get_file_sha256(path):
    """Calcula hash SHA256 de un archivo."""
    if not path or not os.path.exists(path):
        return None
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def format_size(bytes_num):
    """Formatea tamaño en bytes a MB legible."""
    if not bytes_num:
        return "0 MB"
    return f"{bytes_num / (1024 * 1024):.2f} MB"


def is_file_readonly(path):
    """Comprueba si un archivo tiene atributo de solo lectura."""
    if not os.path.exists(path):
        return False
    try:
        return not bool(os.stat(path).st_mode & 0o200)
    except Exception:
        return False


def set_file_readonly(path, readonly=True):
    """Establece o retira el atributo de solo lectura (Windows)."""
    if not os.path.exists(path):
        return False
    try:
        import stat
        if readonly:
            os.chmod(path, stat.S_IREAD)
            subprocess.run(["attrib", "+R", path], capture_output=True)
        else:
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
            subprocess.run(["attrib", "-R", path], capture_output=True)
        return True
    except Exception as e:
        print(f"Error modificando atributos de {path}: {e}")
        return False


def copy_file_with_progress(src, dst, progress_cb=None, chunk_size=128 * 1024):
    """Copia un archivo por bloques invocando un callback de progreso."""
    total = os.path.getsize(src)
    copied = 0
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        while True:
            chunk = fsrc.read(chunk_size)
            if not chunk:
                break
            fdst.write(chunk)
            copied += len(chunk)
            if progress_cb:
                progress_cb(copied, total)
    try:
        shutil.copystat(src, dst)
    except Exception:
        pass


class KoboBackend:
    """Lógica de conexión, detección de idioma del lector y gestión de slots."""

    @staticmethod
    def detect_kobo_locale(kobo_dir):
        """
        Lee el archivo de configuración de Kobo (.kobo/Kobo/Kobo eReader.conf)
        para obtener el parámetro CurrentLocale configurado por el usuario en su lector.
        """
        conf_file = os.path.join(kobo_dir, "Kobo", "Kobo eReader.conf")
        locale_code = "es"  # Por defecto
        if os.path.exists(conf_file):
            try:
                with open(conf_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("CurrentLocale="):
                            val = line.split("=", 1)[1].strip()
                            if val:
                                locale_code = val.split("_")[0].lower()
                                break
            except Exception as e:
                print(f"Aviso leyendo idioma de Kobo: {e}")

        # Determinar slot principal según el idioma
        if locale_code == "en":
            primary_slot = "dicthtml.zip"
        else:
            primary_slot = f"dicthtml-{locale_code}.zip"

        lang_name = LANGUAGE_SLOT_INFO.get(locale_code, {}).get("name", locale_code.upper())
        return locale_code, primary_slot, lang_name

    @staticmethod
    def detect_kobo():
        """Busca una unidad conectada con la estructura de un lector Kobo."""
        drives = [f"{d}:\\" for d in "DEFGHIJKLMNOPQRSTUVWXYZABC"]
        for drive in drives:
            kobo_dir = os.path.join(drive, ".kobo")
            version_file = os.path.join(kobo_dir, "version")
            if os.path.exists(version_file):
                model_name = "Kobo eReader"
                firmware = "Desconocido"
                serial = "N/A"
                try:
                    with open(version_file, "r", encoding="utf-8", errors="ignore") as f:
                        line = f.read().strip()
                        parts = line.split(",")
                        if len(parts) >= 1:
                            serial = parts[0]
                        if len(parts) >= 3:
                            firmware = parts[2]
                        if len(parts) >= 6:
                            hardware_id = parts[5].replace("-", "").lstrip("0")
                            model_name = KOBO_MODELS.get(hardware_id, model_name)

                    for prefix, name in KOBO_MODELS.items():
                        if serial.startswith(prefix):
                            model_name = name
                            break
                except Exception as e:
                    print(f"Error leyendo versión Kobo: {e}")

                dict_dir = os.path.join(kobo_dir, "dict")
                os.makedirs(dict_dir, exist_ok=True)

                # Detectar el idioma del Kobo (CurrentLocale)
                kobo_locale, primary_slot, kobo_lang_name = KoboBackend.detect_kobo_locale(kobo_dir)

                kobo_info = {
                    "drive": drive.rstrip("\\"),
                    "model": model_name,
                    "firmware": firmware,
                    "serial": serial,
                    "dict_dir": dict_dir,
                    "kobo_dir": kobo_dir,
                    "kobo_locale": kobo_locale,
                    "primary_slot": primary_slot,
                    "kobo_lang_name": kobo_lang_name
                }

                # Respaldo oficial automático para la ranura de su idioma si no existe
                official_backup = os.path.join(BACKUPS_DIR, f"official_{primary_slot}")
                expected_spec = OFFICIAL_FACTORY_SPECS.get(primary_slot, {})
                expected_hash = expected_spec.get("sha256")

                # Si ya existía un backup pero era un diccionario personalizado guardado por error, lo limpiamos
                if os.path.exists(official_backup) and expected_hash:
                    if get_file_sha256(official_backup) != expected_hash:
                        try:
                            os.remove(official_backup)
                        except Exception:
                            pass

                if not os.path.exists(official_backup):
                    legacy_path = os.path.join(BACKUPS_DIR, "dicthtml-es_oficial.zip")
                    if os.path.exists(legacy_path) and primary_slot == "dicthtml-es.zip":
                        if not expected_hash or get_file_sha256(legacy_path) == expected_hash:
                            try:
                                shutil.copy2(legacy_path, official_backup)
                            except Exception:
                                pass
                    if not os.path.exists(official_backup):
                        current_primary = os.path.join(dict_dir, primary_slot)
                        if os.path.exists(current_primary):
                            # Un diccionario oficial de fábrica nunca es ReadOnly
                            is_ro = is_file_readonly(current_primary)
                            curr_h = get_file_sha256(current_primary)
                            is_genuine = not is_ro
                            if expected_hash and curr_h != expected_hash:
                                is_genuine = False

                            if is_genuine:
                                try:
                                    shutil.copy2(current_primary, official_backup)
                                except Exception as e:
                                    print(f"Aviso al respaldar oficial: {e}")

                # Auto-importar diccionario personalizado si no está en biblioteca
                KoboBackend.auto_import_existing_device_dict(kobo_info)
                return kobo_info
        return None

    @staticmethod
    def auto_import_existing_device_dict(kobo_info):
        """Preserva en la biblioteca cualquier diccionario encontrado en el lector si no está ya."""
        if not kobo_info:
            return None
        target = os.path.join(kobo_info["dict_dir"], kobo_info["primary_slot"])
        if not os.path.exists(target):
            return None

        # Si el archivo está dañado o es menor a 1 MB, no auto-importar
        if os.path.getsize(target) < 1024 * 1024:
            return None

        h = get_file_sha256(target)
        official_info = KoboBackend.get_official_info(kobo_info["primary_slot"])
        if h == official_info.get("sha256"):
            return None

        catalog = KoboBackend.load_catalog()
        for item in catalog.values():
            if item.get("sha256") == h:
                return None

        label = KNOWN_HASHES.get(h, f"Diccionario Personalizado ({kobo_info['kobo_lang_name']})")
        timestamp = int(time.time() * 1000)
        internal_key = f"dict_imported_{timestamp}.zip"
        dest_zip = os.path.join(LIBRARY_DIR, internal_key)

        try:
            shutil.copy2(target, dest_zip)
            catalog[internal_key] = {
                "name": label,
                "filename": internal_key,
                "target_slot": kobo_info["primary_slot"],
                "size": os.path.getsize(dest_zip),
                "sha256": h,
                "added_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "source_file": "Kobo eReader"
            }
            KoboBackend.save_catalog(catalog)
            return catalog[internal_key]
        except Exception as e:
            print(f"Error al auto-importar diccionario: {e}")
            return None

    @staticmethod
    def get_installed_primary_dict(kobo_info):
        """Retorna información del diccionario instalado en el slot principal del Kobo."""
        if not kobo_info:
            return None
        slot = kobo_info["primary_slot"]
        target = os.path.join(kobo_info["dict_dir"], slot)
        if not os.path.exists(target):
            return None

        h = get_file_sha256(target)
        size = os.path.getsize(target)
        readonly = is_file_readonly(target)
        mtime = os.path.getmtime(target)

        return {
            "slot": slot,
            "path": target,
            "size": size,
            "sha256": h,
            "readonly": readonly,
            "mtime": datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
        }

    @staticmethod
    def get_official_info(primary_slot="dicthtml-es.zip"):
        """Retorna datos del diccionario oficial de fábrica para el slot del idioma del Kobo."""
        backup_path = os.path.join(BACKUPS_DIR, f"official_{primary_slot}")
        if not os.path.exists(backup_path) and primary_slot == "dicthtml-es.zip":
            # Compatibilidad con copia inicial previa
            legacy_path = os.path.join(BACKUPS_DIR, "dicthtml-es_oficial.zip")
            if os.path.exists(legacy_path):
                backup_path = legacy_path

        expected_spec = OFFICIAL_FACTORY_SPECS.get(primary_slot, {})
        expected_hash = expected_spec.get("sha256")
        expected_size = expected_spec.get("size", 13976932)

        if backup_path and os.path.exists(backup_path):
            sz = os.path.getsize(backup_path)
            h = get_file_sha256(backup_path)
            # Si el backup no coincide con las especificaciones conocidas de fábrica, se ignora
            if expected_hash and h != expected_hash:
                return {
                    "size": expected_size,
                    "sha256": expected_hash,
                    "backup_path": None,
                    "is_factory": True
                }
            return {
                "size": sz,
                "sha256": h,
                "backup_path": backup_path,
                "is_factory": True
            }

        # Fallback genérico si aún no hay copia
        return {
            "size": expected_size,
            "sha256": expected_hash,
            "backup_path": None,
            "is_factory": True
        }

    @staticmethod
    def load_catalog():
        """Carga el catálogo local."""
        if os.path.exists(CATALOG_FILE):
            try:
                with open(CATALOG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    @staticmethod
    def save_catalog(catalog):
        """Guarda el catálogo local."""
        try:
            with open(CATALOG_FILE, "w", encoding="utf-8") as f:
                json.dump(catalog, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando catálogo: {e}")

    @staticmethod
    def import_dictionary_file(filepath, default_slot="dicthtml-es.zip"):
        """
        Importa un diccionario (.zip o .rar) a la biblioteca, asignándole
        automáticamente la ranura correcta de Kobo (dicthtml.zip, dicthtml-es.zip, etc.).
        """
        catalog = KoboBackend.load_catalog()
        filename = os.path.basename(filepath)
        clean_name = os.path.splitext(filename)[0]
        clean_title = clean_name.replace("-kobo", "").replace("_", " ").strip()

        # Detección inteligente del slot de destino
        target_slot = detect_target_slot_for_filename(filename, default_slot=default_slot)

        timestamp = int(time.time() * 1000)
        internal_key = f"dict_{timestamp}.zip"
        dest_zip = os.path.join(LIBRARY_DIR, internal_key)

        extracted_dict_zip = None

        with tempfile.TemporaryDirectory() as td:
            lower = filepath.lower()
            if lower.endswith(".zip"):
                with zipfile.ZipFile(filepath, "r") as z:
                    names = z.namelist()
                    inner_zips = [n for n in names if n.lower().startswith("dicthtml") and n.lower().endswith(".zip")]
                    if inner_zips:
                        z.extract(inner_zips[0], td)
                        extracted_dict_zip = os.path.join(td, inner_zips[0])
                    else:
                        extracted_dict_zip = filepath

            elif lower.endswith(".rar"):
                extracted = False
                if os.path.exists(SEVEN_ZIP):
                    res = subprocess.run([SEVEN_ZIP, "e", filepath, "*.zip", f"-o{td}", "-y"], capture_output=True)
                    if res.returncode == 0:
                        extracted = True
                if not extracted:
                    subprocess.run(["tar", "-xf", filepath, "-C", td], capture_output=True)

                for root, dirs, files in os.walk(td):
                    for f in files:
                        if f.lower().endswith(".zip"):
                            extracted_dict_zip = os.path.join(root, f)
                            break
                    if extracted_dict_zip:
                        break
            else:
                raise ValueError("Formato no soportado (.zip o .rar)")

            if not extracted_dict_zip or not os.path.exists(extracted_dict_zip):
                raise RuntimeError(f"No se pudo extraer ningún diccionario de:\n{filename}")

            shutil.copy2(extracted_dict_zip, dest_zip)

        h = get_file_sha256(dest_zip)
        size = os.path.getsize(dest_zip)

        # Si ya existe exactamente el mismo diccionario (mismo sha256), evitar duplicados
        for exist_key, exist_item in catalog.items():
            if exist_item.get("sha256") == h:
                # Ya existe en el catálogo, eliminar el archivo recién copiado y retornar el existente
                if os.path.exists(dest_zip):
                    try:
                        os.remove(dest_zip)
                    except Exception:
                        pass
                return {**exist_item, "is_duplicate": True}

        catalog[internal_key] = {
            "name": clean_title,
            "filename": internal_key,
            "target_slot": target_slot,
            "size": size,
            "sha256": h,
            "added_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "source_file": filename
        }

        KoboBackend.save_catalog(catalog)
        return catalog[internal_key]

    @staticmethod
    def delete_from_catalog(dict_key):
        """Elimina un diccionario de la biblioteca."""
        catalog = KoboBackend.load_catalog()
        if dict_key in catalog:
            item = catalog.pop(dict_key)
            fpath = os.path.join(LIBRARY_DIR, item.get("filename", ""))
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception as e:
                    print(f"Error eliminando {fpath}: {e}")
            KoboBackend.save_catalog(catalog)
            return True
        return False

    @staticmethod
    def set_as_primary(kobo_info, dict_key, protect=True, progress_cb=None):
        """
        Carga un diccionario de la biblioteca en el lector Kobo en su ranura correspondiente
        (dicthtml.zip, dicthtml-es.zip, etc.) con progreso y protección Wi-Fi.
        """
        if not kobo_info:
            raise RuntimeError("Lector no conectado")

        catalog = KoboBackend.load_catalog()
        if dict_key not in catalog:
            raise ValueError("Diccionario no encontrado")

        dict_info = catalog[dict_key]
        src_path = os.path.join(LIBRARY_DIR, dict_info["filename"])
        if not os.path.exists(src_path):
            raise FileNotFoundError("Archivo no encontrado")

        target_slot = dict_info.get("target_slot", kobo_info.get("primary_slot", "dicthtml-es.zip"))
        target_path = os.path.join(kobo_info["dict_dir"], target_slot)

        if os.path.exists(target_path):
            current_h = get_file_sha256(target_path)
            official_info = KoboBackend.get_official_info(target_slot)
            is_in_cat = any(it.get("sha256") == current_h for it in catalog.values())

            if current_h and current_h != official_info.get("sha256") and not is_in_cat:
                label = KNOWN_HASHES.get(current_h, f"Diccionario previo ({target_slot})")
                ts = int(time.time() * 1000)
                auto_key = f"dict_preserved_{ts}.zip"
                auto_dest = os.path.join(LIBRARY_DIR, auto_key)
                try:
                    shutil.copy2(target_path, auto_dest)
                    catalog[auto_key] = {
                        "name": label,
                        "filename": auto_key,
                        "target_slot": target_slot,
                        "size": os.path.getsize(auto_dest),
                        "sha256": current_h,
                        "added_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "source_file": "Preservado del eReader"
                    }
                    KoboBackend.save_catalog(catalog)
                except Exception as e:
                    print(f"Aviso preservando diccionario: {e}")

            set_file_readonly(target_path, False)
            backup_file = f"backup_{target_slot}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            try:
                shutil.copy2(target_path, os.path.join(BACKUPS_DIR, backup_file))
            except Exception as e:
                print(f"Aviso al crear backup: {e}")

        copy_file_with_progress(src_path, target_path, progress_cb=progress_cb)

        if protect:
            set_file_readonly(target_path, True)
        else:
            set_file_readonly(target_path, False)

        return target_slot

    @staticmethod
    def restore_official(kobo_info, progress_cb=None):
        """Restaura el diccionario oficial de fábrica para la ranura del Kobo."""
        if not kobo_info:
            raise RuntimeError("Lector no conectado")

        target_slot = kobo_info.get("primary_slot", "dicthtml-es.zip")
        official_info = KoboBackend.get_official_info(target_slot)
        backup_path = official_info.get("backup_path")

        if not backup_path or not os.path.exists(backup_path):
            raise FileNotFoundError(f"Copia de seguridad oficial ({target_slot}) no encontrada.")

        target_path = os.path.join(kobo_info["dict_dir"], target_slot)
        if os.path.exists(target_path):
            set_file_readonly(target_path, False)

        copy_file_with_progress(backup_path, target_path, progress_cb=progress_cb)
        set_file_readonly(target_path, False)
        return target_slot

    @staticmethod
    def safely_eject(drive_letter):
        """Expulsa la unidad USB de forma segura en Windows."""
        drive = drive_letter.rstrip("\\")
        ps_cmd = f"(New-Object -comObject Shell.Application).Namespace(17).ParseName('{drive}').InvokeVerb('Eject')"
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        return res.returncode == 0


class ModernDictManagerApp(ctk.CTk):
    """Interfaz gráfica de Kobo DictManager con adaptación automática de idioma de Kobo."""

    def __init__(self):
        super().__init__()

        self.current_lang = load_saved_language()

        self.title(self.t("app_title"))
        self.geometry("1020x720")
        self.minsize(920, 620)

        self.current_kobo = None
        self.installed_dict_info = None
        self.catalog = {}
        self.running_detection = True
        self.is_transferring = False

        self.create_layout()

        # Detección inicial inmediata
        self.current_kobo = KoboBackend.detect_kobo()
        self.update_device_ui()

        # Hilo de detección USB continua
        self.detection_thread = threading.Thread(target=self.device_detection_loop, daemon=True)
        self.detection_thread.start()

    def t(self, key, **kwargs):
        """Obtiene la traducción con fallback a inglés."""
        lang_dict = TRANSLATIONS.get(self.current_lang, TRANSLATIONS["en"])
        template = lang_dict.get(key, TRANSLATIONS["en"].get(key, key))
        if kwargs:
            try:
                return template.format(**kwargs)
            except Exception:
                return template
        return template

    def on_language_change(self, selected_lang_name):
        """Cambia el idioma de la aplicación inmediatamente y guarda la preferencia."""
        for code, name in SUPPORTED_LANGUAGES.items():
            if name == selected_lang_name:
                self.current_lang = code
                save_language_preference(code)
                break

        self.title(self.t("app_title"))
        self.add_btn.configure(text=self.t("add_dicts_btn"))
        self.eject_btn.configure(text=self.t("eject_btn"))
        self.open_dict_folder_btn.configure(text=self.t("open_folder_btn"))

        self.update_device_ui()

    def create_layout(self):
        """Crea la estructura visual con barra superior, selector de idioma y lista unificada."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # -------------------------------------------------------------
        # 1. BARRA SUPERIOR: ESTADO DEL DISPOSITIVO, IDIOMA Y ACCIONES
        # -------------------------------------------------------------
        self.header_frame = ctk.CTkFrame(self, corner_radius=10)
        self.header_frame.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="ew")
        self.header_frame.grid_columnconfigure(1, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.header_frame,
            text="📚 Kobo DictManager",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=(15, 12), pady=12, sticky="w")

        self.device_status_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.device_status_frame.grid(row=0, column=1, padx=5, pady=12, sticky="w")

        self.status_indicator = ctk.CTkLabel(
            self.device_status_frame,
            text=self.t("searching"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#FFA500"
        )
        self.status_indicator.pack(side="left")

        self.device_details_label = ctk.CTkLabel(
            self.device_status_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.device_details_label.pack(side="left", padx=(10, 0))

        # Selector de Idioma, Añadir y Expulsar
        self.header_actions = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.header_actions.grid(row=0, column=2, padx=12, pady=10, sticky="e")

        current_lang_display = SUPPORTED_LANGUAGES.get(self.current_lang, "English")
        self.lang_menu = ctk.CTkOptionMenu(
            self.header_actions,
            values=list(SUPPORTED_LANGUAGES.values()),
            command=self.on_language_change,
            width=115,
            height=34,
            dynamic_resizing=False
        )
        self.lang_menu.set(current_lang_display)
        self.lang_menu.pack(side="left", padx=(0, 10))

        self.add_btn = ctk.CTkButton(
            self.header_actions,
            text=self.t("add_dicts_btn"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#28A745",
            hover_color="#218838",
            height=34,
            command=self.on_add_dictionaries
        )
        self.add_btn.pack(side="left", padx=(0, 10))

        self.eject_btn = ctk.CTkButton(
            self.header_actions,
            text=self.t("eject_btn"),
            width=100,
            height=34,
            command=self.on_eject_clicked,
            state="disabled",
            fg_color="#D9534F",
            hover_color="#C9302C"
        )
        self.eject_btn.pack(side="left")

        # -------------------------------------------------------------
        # 2. RECUADRO ÚNICO UNIFICADO: TODOS LOS DICCIONARIOS
        # -------------------------------------------------------------
        self.main_container = ctk.CTkFrame(self, corner_radius=10)
        self.main_container.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        self.list_header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.list_header.grid(row=0, column=0, padx=15, pady=(12, 4), sticky="ew")
        self.list_header.grid_columnconfigure(0, weight=1)

        self.list_title = ctk.CTkLabel(
            self.list_header,
            text=self.t("ereader_dicts_title", slot_desc="..."),
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.list_title.grid(row=0, column=0, sticky="w")

        self.scroll_frame = ctk.CTkScrollableFrame(self.main_container, corner_radius=8)
        self.scroll_frame.grid(row=1, column=0, padx=15, pady=(5, 12), sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # -------------------------------------------------------------
        # 3. BARRA INFERIOR / ESTADO Y EXPLORADOR
        # -------------------------------------------------------------
        self.footer_frame = ctk.CTkFrame(self, height=45, corner_radius=8)
        self.footer_frame.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="ew")
        self.footer_frame.grid_columnconfigure(0, weight=1)

        self.status_bar = ctk.CTkLabel(
            self.footer_frame,
            text=self.t("ready_status"),
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.status_bar.grid(row=0, column=0, padx=15, pady=8, sticky="w")

        self.open_dict_folder_btn = ctk.CTkButton(
            self.footer_frame,
            text=self.t("open_folder_btn"),
            width=220,
            height=28,
            fg_color="#333333",
            hover_color="#444444",
            command=self.on_open_dict_folder
        )
        self.open_dict_folder_btn.grid(row=0, column=1, padx=10, pady=6, sticky="e")

    # -----------------------------------------------------------------
    # DIÁLOGO MODAL CON BARRA DE PROGRESO
    # -----------------------------------------------------------------
    def create_progress_dialog(self, title_text, item_name, is_indeterminate=False):
        """Crea ventana modal con barra de progreso."""
        dlg = ctk.CTkToplevel(self)
        dlg.title(title_text)
        dlg.attributes("-topmost", True)
        dlg.transient(self)
        dlg.grab_set()

        self.update_idletasks()
        win_w, win_h = 480, 200
        x = self.winfo_x() + (self.winfo_width() - win_w) // 2
        y = self.winfo_y() + (self.winfo_height() - win_h) // 2
        dlg.geometry(f"{win_w}x{win_h}+{x}+{y}")
        dlg.resizable(False, False)

        dlg.protocol("WM_DELETE_WINDOW", lambda: None)

        title_lbl = ctk.CTkLabel(
            dlg,
            text=title_text,
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_lbl.pack(pady=(20, 4))

        name_lbl = ctk.CTkLabel(
            dlg,
            text=item_name,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=("#1976D2", "#90CAF9")
        )
        name_lbl.pack(pady=(0, 12))

        pbar = ctk.CTkProgressBar(
            dlg,
            width=400,
            height=14,
            corner_radius=7,
            mode="indeterminate" if is_indeterminate else "determinate"
        )
        pbar.pack(pady=4)

        if is_indeterminate:
            pbar.start()
        else:
            pbar.set(0.0)

        status_lbl = ctk.CTkLabel(
            dlg,
            text="...",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        status_lbl.pack(pady=(6, 4))

        hint_lbl = ctk.CTkLabel(
            dlg,
            text=self.t("keep_usb_warning"),
            font=ctk.CTkFont(size=11),
            text_color="#FFA500"
        )
        hint_lbl.pack(pady=(0, 15))

        return dlg, pbar, status_lbl

    # -----------------------------------------------------------------
    # DETECCIÓN DE HARDWARE Y REFRESH
    # -----------------------------------------------------------------
    def device_detection_loop(self):
        """Revisa periódicamente la conexión USB si no se está transfiriendo."""
        last_state = None
        while self.running_detection:
            try:
                if not self.is_transferring:
                    kobo_info = KoboBackend.detect_kobo()
                    current_state = kobo_info["drive"] if kobo_info else None

                    if current_state != last_state:
                        last_state = current_state
                        self.current_kobo = kobo_info
                        self.after(0, self.update_device_ui)

                time.sleep(2)
            except Exception as e:
                print(f"Error en detección: {e}")
                time.sleep(3)

    def update_device_ui(self):
        """Actualiza la interfaz cuando cambia la conexión del Kobo o el idioma."""
        if self.current_kobo:
            model = self.current_kobo["model"]
            drive = self.current_kobo["drive"]
            fw = self.current_kobo["firmware"]
            kobo_lang = self.current_kobo["kobo_lang_name"]
            slot = self.current_kobo["primary_slot"]

            self.status_indicator.configure(
                text=self.t("connected", model=model, drive=drive, kobo_lang=kobo_lang),
                text_color="#5CB85C"
            )
            self.device_details_label.configure(
                text=self.t("device_info", fw=fw, serial=self.current_kobo['serial'][:8])
            )
            self.list_title.configure(
                text=self.t("ereader_dicts_title", slot_desc=f"{kobo_lang} • {slot}")
            )
            self.eject_btn.configure(state="normal")
            self.open_dict_folder_btn.configure(state="normal")
            self.status_bar.configure(text=self.t("device_ready_status", model=model, kobo_lang=kobo_lang, drive=drive))
        else:
            self.status_indicator.configure(
                text=self.t("waiting_usb"),
                text_color="#FFA500"
            )
            self.device_details_label.configure(
                text=self.t("connect_prompt")
            )
            self.list_title.configure(
                text=self.t("ereader_dicts_title", slot_desc="...")
            )
            self.eject_btn.configure(state="disabled")
            self.open_dict_folder_btn.configure(state="disabled")
            self.status_bar.configure(text=self.t("waiting_usb"))

        self.refresh_dictionaries_view()

    def refresh_dictionaries_view(self):
        """Lee el diccionario actualmente instalado en el slot del Kobo y recarga la lista."""
        if self.current_kobo:
            self.installed_dict_info = KoboBackend.get_installed_primary_dict(self.current_kobo)
        else:
            self.installed_dict_info = None

        self.catalog = KoboBackend.load_catalog()
        self.render_all_dictionaries()

    def render_all_dictionaries(self):
        """Dibuja todos los diccionarios garantizando que SOLO UNO esté marcado como activo."""
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        current_active_hash = self.installed_dict_info["sha256"] if self.installed_dict_info else None
        is_readonly = self.installed_dict_info["readonly"] if self.installed_dict_info else False
        primary_slot = self.current_kobo["primary_slot"] if self.current_kobo else "dicthtml-es.zip"
        kobo_lang = self.current_kobo["kobo_lang_name"] if self.current_kobo else "Español"

        # Comprobamos primero si el diccionario cargado en el lector coincide con uno de la biblioteca
        active_catalog_key = None
        for key, item in self.catalog.items():
            if current_active_hash and current_active_hash == item.get("sha256"):
                active_catalog_key = key
                break

        # -------------------------------------------------------------
        # 1. ELEMENTO FIJO: DICCIONARIO OFICIAL DE FÁBRICA DEL KOBO
        # -------------------------------------------------------------
        official_info = KoboBackend.get_official_info(primary_slot)
        is_official_active = False
        if not active_catalog_key and current_active_hash and current_active_hash == official_info.get("sha256"):
            is_official_active = True

        self.create_dict_card(
            parent=self.scroll_frame,
            key="__official_factory_kobo__",
            title=self.t("official_dict_name", lang=kobo_lang),
            desc=self.t("official_dict_desc", slot=primary_slot),
            slot_name=primary_slot,
            size_bytes=official_info["size"],
            is_active=is_official_active,
            is_factory=True,
            is_readonly=is_readonly if is_official_active else False
        )

        # -------------------------------------------------------------
        # 2. DICCIONARIOS EN LA BIBLIOTECA DEL USUARIO
        # -------------------------------------------------------------
        for key, item in self.catalog.items():
            target_slot = item.get("target_slot", primary_slot)
            is_active = (key == active_catalog_key)

            file_name = item.get('source_file', item.get('filename', ''))
            added_date = item.get('added_date', '')
            desc_text = self.t("file_added_label", file=file_name, date=added_date)

            self.create_dict_card(
                parent=self.scroll_frame,
                key=key,
                title=item.get("name", key),
                desc=desc_text,
                slot_name=target_slot,
                size_bytes=item.get("size", 0),
                is_active=is_active,
                is_factory=False,
                is_readonly=is_readonly if is_active else False
            )

    def create_dict_card(self, parent, key, title, desc, slot_name, size_bytes, is_active, is_factory, is_readonly):
        """Crea una fila interactiva para cada diccionario con distinción de color."""
        if is_active:
            card_bg = ("#E8F5E9", "#183624")
            card_border = ("#4CAF50", "#2ECC71")
            card_border_width = 2
        else:
            card_bg = ("#F5F6F8", "#242526")
            card_border = ("#E0E0E0", "#383838")
            card_border_width = 1

        card = ctk.CTkFrame(
            parent,
            corner_radius=8,
            fg_color=card_bg,
            border_color=card_border,
            border_width=card_border_width
        )
        card.pack(fill="x", padx=5, pady=6)
        card.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", padx=14, pady=(10, 3))

        title_lbl = ctk.CTkLabel(
            title_row,
            text=title,
            font=ctk.CTkFont(size=15, weight="bold")
        )
        title_lbl.pack(side="left")

        # Badge del slot de destino (ej: dicthtml.zip o dicthtml-es.zip)
        slot_badge = ctk.CTkLabel(
            title_row,
            text=f"🎯 {slot_name}",
            font=ctk.CTkFont(size=11),
            fg_color=("#E0E0E0", "#333333"),
            corner_radius=4,
            padx=7,
            pady=2
        )
        slot_badge.pack(side="left", padx=8)

        if is_factory:
            factory_badge = ctk.CTkLabel(
                title_row,
                text=self.t("factory_badge"),
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=("#E3F2FD", "#1A365D"),
                text_color=("#1976D2", "#90CAF9"),
                corner_radius=4,
                padx=8,
                pady=2
            )
            factory_badge.pack(side="left", padx=6)

        if is_active:
            active_badge = ctk.CTkLabel(
                title_row,
                text=self.t("active_badge"),
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#28A745",
                text_color="white",
                corner_radius=4,
                padx=9,
                pady=2
            )
            active_badge.pack(side="left", padx=6)

            if is_readonly:
                prot_badge = ctk.CTkLabel(
                    title_row,
                    text=self.t("protected_badge"),
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color=("#D4EDDA", "#1E4620"),
                    text_color=("#155724", "#A3E9A4"),
                    corner_radius=4,
                    padx=7,
                    pady=2
                )
                prot_badge.pack(side="left", padx=6)
            else:
                unprot_badge = ctk.CTkLabel(
                    title_row,
                    text=self.t("unprotected_badge"),
                    font=ctk.CTkFont(size=11),
                    fg_color=("#FFF3CD", "#4D3800"),
                    text_color=("#856404", "#FFEBAA"),
                    corner_radius=4,
                    padx=7,
                    pady=2
                )
                unprot_badge.pack(side="left", padx=6)

        if desc:
            desc_lbl = ctk.CTkLabel(
                card,
                text=desc,
                font=ctk.CTkFont(size=12),
                text_color=("#555555", "#AAAAAA"),
                wraplength=640,
                justify="left"
            )
            desc_lbl.pack(anchor="w", padx=14, pady=(0, 4))

        bottom_row = ctk.CTkFrame(card, fg_color="transparent")
        bottom_row.pack(fill="x", padx=14, pady=(0, 10))

        sz_str = format_size(size_bytes)
        size_lbl = ctk.CTkLabel(
            bottom_row,
            text=self.t("size_label", size=sz_str),
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        size_lbl.pack(side="left")

        actions_frame = ctk.CTkFrame(bottom_row, fg_color="transparent")
        actions_frame.pack(side="right")

        if not is_factory and key != "__current_installed_unregistered__":
            trash_btn = ctk.CTkButton(
                actions_frame,
                text="🗑️",
                width=38,
                height=34,
                corner_radius=6,
                fg_color="#D9534F",
                hover_color="#C9302C",
                font=ctk.CTkFont(size=15),
                anchor="center",
                command=lambda k=key: self.on_delete_dictionary(k)
            )
            trash_btn.pack(side="right", padx=(8, 0))

        if is_active:
            btn = ctk.CTkButton(
                actions_frame,
                text=self.t("currently_active_btn"),
                width=180,
                height=34,
                state="disabled",
                fg_color="#28A745",
                font=ctk.CTkFont(weight="bold")
            )
            btn.pack(side="right")
        else:
            action_text = self.t("load_btn") if not is_factory else self.t("restore_official_btn")
            btn = ctk.CTkButton(
                actions_frame,
                text=action_text,
                width=190,
                height=34,
                command=lambda k=key, fact=is_factory, s=slot_name: self.on_activate_dictionary(k, fact, s)
            )
            btn.pack(side="right")

    # -----------------------------------------------------------------
    # ACCIONES DEL USUARIO (CON ADAPTACIÓN DE SLOT AUTOMÁTICA)
    # -----------------------------------------------------------------
    def on_add_dictionaries(self):
        """Importa archivos asignando automáticamente la ranura correspondiente al Kobo."""
        files = filedialog.askopenfilenames(
            title=self.t("select_dicts_dialog_title"),
            filetypes=[
                (self.t("filetypes_desc"), "*.zip *.rar"),
                ("ZIP", "*.zip"),
                ("RAR", "*.rar"),
                ("*.*", "*.*")
            ]
        )
        if not files:
            return

        default_slot = self.current_kobo["primary_slot"] if self.current_kobo else "dicthtml-es.zip"

        dlg, pbar, status_lbl = self.create_progress_dialog(
            title_text=self.t("importing_title"),
            item_name=f"{len(files)} files",
            is_indeterminate=True
        )

        def worker():
            added_names = []
            duplicates = []
            errors = []
            for fpath in files:
                try:
                    entry = KoboBackend.import_dictionary_file(fpath, default_slot=default_slot)
                    if entry.get("is_duplicate"):
                        duplicates.append((os.path.basename(fpath), entry.get("name", "Diccionario")))
                    else:
                        added_names.append(f"{entry['name']} (🎯 {entry['target_slot']})")
                except Exception as e:
                    errors.append(f"{os.path.basename(fpath)}: {e}")

            def done():
                try:
                    dlg.grab_release()
                    dlg.destroy()
                except Exception:
                    pass

                self.refresh_dictionaries_view()

                if added_names:
                    msg = self.t("added_success_msg", count=len(added_names), list="\n• ".join(added_names))
                    if duplicates:
                        msg += "\n\n" + "\n".join([f"⚠️ '{f}' ya estaba cargado como '{n}'." for f, n in duplicates])
                    if errors:
                        msg += "\n\nErrors:\n" + "\n".join(errors)
                    messagebox.showinfo(self.t("added_success_title"), msg)
                    self.status_bar.configure(text=f"{len(added_names)} ok.")
                elif duplicates:
                    dup_text = "\n".join([f"• '{f}' ya está en tu lista como '{n}'." for f, n in duplicates])
                    messagebox.showwarning(
                        self.t("dict_already_in_library_title"),
                        f"El diccionario seleccionado ya está cargado en tu lista:\n\n{dup_text}\n\nNo es necesario volver a añadirlo."
                    )
                    self.status_bar.configure(text="El diccionario ya estaba cargado.")
                else:
                    if errors:
                        messagebox.showerror("Error", "\n".join(errors))

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def on_activate_dictionary(self, dict_key, is_factory, slot_name):
        """Carga el diccionario en el lector en el slot correspondiente."""
        if not self.current_kobo:
            messagebox.showwarning("Notice", self.t("not_connected_warning"))
            return

        current_active_hash = self.installed_dict_info["sha256"] if self.installed_dict_info else None

        if is_factory:
            official_info = KoboBackend.get_official_info(slot_name)
            target_dict_hash = official_info.get("sha256")
            dict_name = self.t("official_dict_name", lang=self.current_kobo['kobo_lang_name'])
        else:
            dict_info = self.catalog.get(dict_key, {})
            target_dict_hash = dict_info.get("sha256")
            dict_name = dict_info.get("name", dict_key)

        # Advertencia si ya es el mismo diccionario que está activo en el lector
        if current_active_hash and target_dict_hash and current_active_hash == target_dict_hash:
            messagebox.showinfo(
                self.t("dict_already_active_title"),
                self.t("dict_already_active_msg", name=dict_name)
            )
            return

        if is_factory:
            confirm = messagebox.askyesno(
                self.t("confirm_restore_title"),
                self.t("confirm_restore_msg", slot=slot_name)
            )
        else:
            confirm = messagebox.askyesno(
                self.t("confirm_load_title"),
                self.t("confirm_load_msg", name=dict_name, model=self.current_kobo['model'], slot=slot_name)
            )

        if not confirm:
            return

        self.is_transferring = True
        dlg, pbar, status_lbl = self.create_progress_dialog(
            title_text=self.t("uploading_title"),
            item_name=dict_name,
            is_indeterminate=False
        )

        def progress_cb(copied, total):
            frac = min(1.0, max(0.0, copied / total)) if total > 0 else 0.0
            mb_copied = copied / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            pct = int(frac * 100)

            def update_ui():
                try:
                    pbar.set(frac)
                    status_lbl.configure(
                        text=self.t("copying_status", slot=slot_name, pct=pct, copied=mb_copied, total=mb_total)
                    )
                except Exception:
                    pass

            self.after(0, update_ui)

        def worker():
            err = None
            used_slot = slot_name
            try:
                if is_factory:
                    used_slot = KoboBackend.restore_official(self.current_kobo, progress_cb=progress_cb)
                else:
                    used_slot = KoboBackend.set_as_primary(self.current_kobo, dict_key, protect=True, progress_cb=progress_cb)
            except Exception as e:
                err = str(e)

            def finish():
                self.is_transferring = False
                try:
                    dlg.grab_release()
                    dlg.destroy()
                except Exception:
                    pass

                self.refresh_dictionaries_view()

                if err:
                    messagebox.showerror("Error", f"Error:\n{err}")
                    self.status_bar.configure(text=f"Error: {err}")
                else:
                    self.status_bar.configure(text=f"OK: {dict_name} ({used_slot})")
                    if is_factory:
                        messagebox.showinfo(
                            self.t("restore_success_title"),
                            self.t("restore_success_msg", slot=used_slot)
                        )
                    else:
                        messagebox.showinfo(
                            self.t("load_success_title"),
                            self.t("load_success_msg", name=dict_name, slot=used_slot)
                        )

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def on_delete_dictionary(self, dict_key):
        """Elimina un diccionario de la lista."""
        dict_info = self.catalog.get(dict_key, {})
        name = dict_info.get("name", dict_key)

        confirm = messagebox.askyesno(
            self.t("confirm_delete_title"),
            self.t("confirm_delete_msg", name=name)
        )
        if confirm:
            KoboBackend.delete_from_catalog(dict_key)
            self.refresh_dictionaries_view()
            self.status_bar.configure(text=f"Deleted: {name}")

    def on_eject_clicked(self):
        """Expulsa la unidad USB con seguridad."""
        if not self.current_kobo:
            return
        drive = self.current_kobo["drive"]
        model = self.current_kobo["model"]

        confirm = messagebox.askyesno(
            self.t("eject_confirm_title"),
            self.t("eject_confirm_msg", model=model, drive=drive)
        )
        if not confirm:
            return

        success = KoboBackend.safely_eject(drive)
        if success:
            messagebox.showinfo(
                self.t("eject_success_title"),
                self.t("eject_success_msg", model=model)
            )
            self.current_kobo = None
            self.update_device_ui()
        else:
            messagebox.showwarning(
                self.t("eject_confirm_title"),
                self.t("eject_warning_msg")
            )

    def on_open_dict_folder(self):
        """Abre la carpeta de diccionarios en el lector."""
        if self.current_kobo and os.path.exists(self.current_kobo["dict_dir"]):
            os.startfile(self.current_kobo["dict_dir"])


if __name__ == "__main__":
    app = ModernDictManagerApp()
    app.mainloop()
