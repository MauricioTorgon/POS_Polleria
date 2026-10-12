import os
import json
import shutil
import sqlite3
import urllib.request
import urllib.error
import mimetypes
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'backup_config.json')


def load_config():
    default_config = {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
        "backup_interval_minutes": 120,
        "backup_on_caja_cierre": True,
        "keep_local_backups": 15
    }
    if not os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
        except Exception:
            pass
        return default_config
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            default_config.update(cfg)
            return default_config
    except Exception:
        return default_config


def save_config(data):
    cfg = load_config()
    cfg.update(data)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4)
    return cfg


def get_db_path():
    base_dir = os.path.dirname(__file__)
    # SQLite usa instance/pos.db por defecto en Flask
    db_path = os.path.join(base_dir, 'instance', 'pos.db')
    if not os.path.exists(db_path):
        db_path = os.path.join(base_dir, 'pos.db')
    return db_path


def create_local_backup():
    """Genera una copia consistente de la base de datos usando la API de backup de SQLite."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return None

    backups_dir = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(backups_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"pos_backup_{timestamp}.db"
    dest_path = os.path.join(backups_dir, backup_filename)

    try:
        # SQLite backup API para consistencia incluso si la base está siendo escrita
        src_conn = sqlite3.connect(db_path)
        dest_conn = sqlite3.connect(dest_path)
        with dest_conn:
            src_conn.backup(dest_conn)
        dest_conn.close()
        src_conn.close()
    except Exception:
        # Fallback si estuviera bloqueada
        shutil.copy2(db_path, dest_path)

    clean_old_backups(backups_dir)
    return dest_path


def clean_old_backups(backups_dir):
    cfg = load_config()
    max_keep = cfg.get("keep_local_backups", 15)
    try:
        files = [os.path.join(backups_dir, f) for f in os.listdir(backups_dir) if f.endswith('.db')]
        files.sort(key=os.path.getmtime)
        while len(files) > max_keep:
            to_remove = files.pop(0)
            try:
                os.remove(to_remove)
            except Exception:
                pass
    except Exception:
        pass


def send_file_to_telegram(bot_token, chat_id, file_path, caption=""):
    """Envía un archivo a un chat o canal de Telegram usando urllib puro (sin dependencias extra)."""
    boundary = '----TelegramBoundary' + datetime.now().strftime('%Y%m%d%H%M%S%f')
    filename = os.path.basename(file_path)

    with open(file_path, 'rb') as f:
        file_bytes = f.read()

    body = bytearray()
    
    # Campo chat_id
    body.extend(f'--{boundary}\r\n'.encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode('utf-8'))

    # Campo caption
    if caption:
        body.extend(f'--{boundary}\r\n'.encode('utf-8'))
        body.extend(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode('utf-8'))

    # Archivo documento
    body.extend(f'--{boundary}\r\n'.encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode('utf-8'))
    body.extend(b'Content-Type: application/octet-stream\r\n\r\n')
    body.extend(file_bytes)
    body.extend(b'\r\n')

    # Fin del multipart
    body.extend(f'--{boundary}--\r\n'.encode('utf-8'))

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    req = urllib.request.Request(url, data=bytes(body))
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data.get('ok', False), res_data
    except Exception as e:
        return False, str(e)


def send_message_to_telegram(bot_token, chat_id, text):
    """Envía un mensaje de texto simple."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return True, "Mensaje enviado"
    except Exception as e:
        return False, str(e)


def ejecutar_respaldo(motivo="Programado"):
    """Genera respaldo local y lo envía a Telegram si está configurado."""
    cfg = load_config()
    backup_file = create_local_backup()
    if not backup_file:
        return False, "No se encontró el archivo de base de datos"

    if not cfg.get("enabled"):
        return True, f"Respaldo local creado exitosamente en {os.path.basename(backup_file)}"

    bot_token = cfg.get("bot_token", "").strip()
    chat_id = cfg.get("chat_id", "").strip()

    if not bot_token or not chat_id:
        return True, "Respaldo local creado. Configura Bot Token y Chat ID para envío automático a la nube."

    caption = (
        f"📦 <b>Respaldo POS Verdulería</b>\n"
        f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"📌 Motivo: <i>{motivo}</i>\n"
        f"💾 Archivo: <code>{os.path.basename(backup_file)}</code>"
    )

    ok, result = send_file_to_telegram(bot_token, chat_id, backup_file, caption=caption)
    if ok:
        return True, f"Respaldo enviado exitosamente a Telegram ({os.path.basename(backup_file)})"
    else:
        return False, f"Respaldo local creado, pero falló envío a Telegram: {result}"
