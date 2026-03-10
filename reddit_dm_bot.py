"""
Reddit DM Auto-Reply Bot
========================
Monitorea el inbox y responde automáticamente a mensajes privados
con rotación de mensajes y delays aleatorios para evitar detección.

Requisitos:
    pip install praw

Variables de entorno necesarias (.env o en el panel de Render/Railway):
    REDDIT_CLIENT_ID
    REDDIT_CLIENT_SECRET
    REDDIT_USERNAME
    REDDIT_PASSWORD
    REDDIT_USER_AGENT  (ej: "dm_bot/1.0 by u/TuUsuario")
"""

import praw
import time
import random
import logging
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ─── Configuración ──────────────────────────────────────────────────────────
# Cuánto tiempo ignorar a un usuario después de haberle respondido (días)
COOLDOWN_DAYS = 7

# Delay aleatorio entre cada respuesta (segundos) — humaniza el comportamiento
DELAY_MIN = 180   # 3 minutos
DELAY_MAX = 480   # 8 minutos

# Cuánto tiempo esperar entre cada ciclo de polling (segundos)
POLL_INTERVAL = 60

# Archivo local para guardar a quién ya le respondimos
COOLDOWN_FILE = "replied_users.json"


# ─── Mensajes de respuesta (rotación aleatoria) ──────────────────────────────
# ⚠️  PERSONALIZA estos mensajes con tu propio estilo/link
REPLY_MESSAGES = [
    """Oi, obrigada pela mensagem 🙂 Estou bem ocupada aqui, mas passo mais tempo no meu Telegram onde posto conteúdo exclusivo e consigo responder todo mundo. Me encontra lá: https://jack-loppes-site.onrender.com/""",

    """Oi! Que bom ter notícia sua 😊 Aqui no Reddit não consigo responder tudo, mas no meu Telegram estou bem mais ativa e posto bastante coisa exclusiva. Passa lá: https://jack-loppes-site.onrender.com/""",

    """Oi, obrigada por entrar em contato! Acabo não conseguindo acompanhar tudo por aqui, mas no meu Telegram posto conteúdo exclusivo e respondo muito mais. Te espero lá 🙂 https://jack-loppes-site.onrender.com/""",
]


# ─── Persistencia de cooldown ────────────────────────────────────────────────
def load_cooldowns() -> dict:
    if Path(COOLDOWN_FILE).exists():
        with open(COOLDOWN_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cooldowns(data: dict):
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_in_cooldown(username: str, cooldowns: dict) -> bool:
    if username not in cooldowns:
        return False
    last_replied = datetime.fromisoformat(cooldowns[username])
    return datetime.now() - last_replied < timedelta(days=COOLDOWN_DAYS)


def set_cooldown(username: str, cooldowns: dict):
    cooldowns[username] = datetime.now().isoformat()
    save_cooldowns(cooldowns)


# ─── Inicializar Reddit ──────────────────────────────────────────────────────
def init_reddit() -> praw.Reddit:
    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "dm_bot/1.0"),
    )
    log.info(f"Autenticado como: u/{reddit.user.me()}")
    return reddit


# ─── Procesar un mensaje ─────────────────────────────────────────────────────
def process_message(message, cooldowns: dict):
    author = str(message.author) if message.author else None

    # Ignorar mensajes del sistema o sin autor
    if not author or author.lower() in ("automoderator", "reddit"):
        message.mark_read()
        return

    # Ignorar si ya le respondimos recientemente
    if is_in_cooldown(author, cooldowns):
        log.info(f"Skipping u/{author} — en cooldown")
        message.mark_read()
        return

    # Elegir mensaje aleatorio
    reply_text = random.choice(REPLY_MESSAGES)

    # Delay humanizado antes de responder
    delay = random.randint(DELAY_MIN, DELAY_MAX)
    log.info(f"Respondiendo a u/{author} en {delay // 60}m {delay % 60}s...")
    time.sleep(delay)

    try:
        message.reply(reply_text)
        set_cooldown(author, cooldowns)
        message.mark_read()
        log.info(f"✓ Respondido a u/{author}")
    except Exception as e:
        log.error(f"Error respondiendo a u/{author}: {e}")


# ─── Loop principal ──────────────────────────────────────────────────────────
def run():
    reddit = init_reddit()
    cooldowns = load_cooldowns()
    log.info("Bot iniciado. Monitoreando inbox...")

    while True:
        try:
            unread = list(reddit.inbox.unread(limit=None))

            if not unread:
                log.info("Inbox limpio, esperando...")
            else:
                log.info(f"{len(unread)} mensajes sin leer encontrados")

            for item in unread:
                # Solo procesar DMs directos, no replies a comentarios
                if item.type == "unknown":
                    # message requests — mismo tratamiento
                    process_message(item, cooldowns)
                elif hasattr(item, "fullname") and item.fullname.startswith("t4_"):
                    # t4_ = mensaje privado directo
                    process_message(item, cooldowns)
                else:
                    # Comentario/reply — solo marcar como leído, no responder
                    item.mark_read()

        except praw.exceptions.APIException as e:
            log.error(f"Reddit API error: {e}")
            time.sleep(60)
        except Exception as e:
            log.error(f"Error inesperado: {e}")
            time.sleep(30)

        log.info(f"Ciclo completo. Próximo check en {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
