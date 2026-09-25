import os
import logging
import html
import httpx

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from sources.soundcloud import SoundCloudSource


# =========================================================
# НАСТРОЙКИ
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

ITUNES_API = "https://itunes.apple.com/search"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ
# =========================================================

user_results = {}
user_favorites = {}


# =========================================================
# SOUNDCLOUD
# =========================================================

soundcloud = SoundCloudSource()


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔎 Поиск", callback_data="search"),
        ],
        [
            InlineKeyboardButton("❤️ Моя музыка", callback_data="favorites"),
        ],
        [
            InlineKeyboardButton("⚙️ Источники", callback_data="sources"),
        ],
        [
            InlineKeyboardButton("ℹ️ Помощь", callback_data="help"),
        ],
    ])


# =========================================================
# КНОПКИ РЕЗУЛЬТАТОВ
# =========================================================

def results_keyboard(tracks):
    buttons = []

    for index, track in enumerate(tracks):
        title = track.get("trackName", "Без названия")
        artist = track.get("artistName", "Неизвестный исполнитель")

        text = f"🎵 {title} — {artist}"

        if len(text) > 60:
            text = text[:57] + "..."

        buttons.append([
            InlineKeyboardButton(
                text,
                callback_data=f"play_{index}",
            )
        ])

    buttons.append([
        InlineKeyboardButton("🔎 Новый поиск", callback_data="search")
    ])

    buttons.append([
        InlineKeyboardButton("❤️ Моя музыка", callback_data="favorites")
    ])

    buttons.append([
        InlineKeyboardButton("⬅️ Меню", callback_data="menu")
    ])

    return InlineKeyboardMarkup(buttons)


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>🎵 MUSIC BOT</b>\n\n"
        "Поиск музыки в нескольких источниках.\n\n"
        "Нажми <b>🔎 Поиск</b> и введи:\n"
        "• исполнителя\n"
        "• название трека\n"
        "• исполнителя + название\n\n"
        "Например:\n"
        "<code>The Weeknd</code>\n"
        "<code>Blinding Lights</code>\n"
        "<code>Моя Мишель</code>\n"
        "<code>MACAN</code>\n"
        "<code>Miyagi</code>"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


# =========================================================
# ПОИСК
# =========================================================

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if update.callback_query:
        await update.callback_query.answer()

        await update.callback_query.message.reply_text(
            "🔎 Введи название трека или исполнителя:"
        )

        context.user_data["waiting_for_search"] = True
        return

    if not context.user_data.get("waiting_for_search"):
        return

    context.user_data["waiting_for_search"] = False

    query = update.message.text.strip()

    if not query:
        await update.message.reply_text(
            "❌ Введи название трека или исполнителя."
        )
        return

    await update.message.reply_text(
        f"🔎 Ищу: <b>{html.escape(query)}</b>...",
        parse_mode="HTML",
    )

    tracks = []

    # -----------------------------------------------------
    # iTunes / Apple Music
    # -----------------------------------------------------

    try:
        params = {
            "term": query,
            "media": "music",
            "entity": "song",
            "country": "RU",
            "lang": "ru_ru",
            "limit": 10,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                ITUNES_API,
                params=params,
            )

            response.raise_for_status()

            data = response.json()

        tracks = data.get("results", [])

        # Fallback без country
        if not tracks:
            params.pop("country", None)
            params.pop("lang", None)

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    ITUNES_API,
                    params=params,
                )

                response.raise_for_status()

                data = response.json()

            tracks = data.get("results", [])

    except Exception as error:
        logger.exception(
            "Ошибка поиска iTunes: %s",
            error,
        )

    # -----------------------------------------------------
    # СОХРАНЯЕМ РЕЗУЛЬТАТЫ
    # -----------------------------------------------------

    user_results[user_id] = {
        "query": query,
        "tracks": tracks,
    }

    if not tracks:
        await update.message.reply_text(
            "😔 Ничего не найдено.\n\n"
            "Попробуй изменить запрос.",
            reply_markup=main_menu_keyboard(),
        )
        return

    text = (
        "<b>🎵 MUSIC BOT</b>\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"🔎 Поиск: <b>{html.escape(query)}</b>\n\n"
        "👇 Выбери трек:"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=results_keyboard(tracks),
    )


# =========================================================
# ВОСПРОИЗВЕДЕНИЕ ТРЕКА
# =========================================================

async def play_track(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    index: int,
):
    query = update.callback_query
    user_id = update.effective_user.id

    await query.answer()

    data = user_results.get(user_id)

    if not data:
        await query.message.reply_text(
            "❌ Результаты поиска устарели.\n"
            "Сделай новый поиск."
        )
        return

    tracks = data.get("tracks", [])

    if index < 0 or index >= len(tracks):
        await query.message.reply_text(
            "❌ Трек не найден."
        )
        return

    track = tracks[index]

    title = track.get(
        "trackName",
        "Без названия",
    )

    artist = track.get(
        "artistName",
        "Неизвестный исполнитель",
    )

    preview_url = track.get("previewUrl")
    track_url = track.get("trackViewUrl")

    # -----------------------------------------------------
    # ПРЕВЬЮ
    # -----------------------------------------------------

    if preview_url:
        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
            ) as client:

                response = await client.get(preview_url)
                response.raise_for_status()

                audio_data = response.content

            await query.message.reply_audio(
                audio=audio_data,
                title=title,
                performer=artist,
                caption=(
                    f"🎵 <b>{html.escape(title)}</b>\n"
                    f"🎤 {html.escape(artist)}\n\n"
                    "▶️ 30-секундное превью"
                ),
                parse_mode="HTML",
            )

            return

        except Exception as error:
            logger.exception(
                "Ошибка отправки превью: %s",
                error,
            )

    # -----------------------------------------------------
    # ЕСЛИ ПРЕВЬЮ НЕТ
    # -----------------------------------------------------

    buttons = []

    if track_url:
        buttons.append([
            InlineKeyboardButton(
                "🎵 Открыть трек",
                url=track_url,
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Назад к результатам",
            callback_data="back_results",
        )
    ])

    await query.message.reply_text(
        (
            f"🎵 <b>{html.escape(title)}</b>\n"
            f"🎤 {html.escape(artist)}\n\n"
            "Для этого трека доступна ссылка "
            "на официальный источник."
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# =========================================================
# ИЗБРАННОЕ
# =========================================================

def favorite_keyboard(track_index):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "▶️ Открыть",
                callback_data=f"favplay_{track_index}",
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Удалить",
                callback_data=f"favorite_{track_index}",
            )
        ],
    ])


async def toggle_favorite(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    index: int,
):
    query = update.callback_query
    user_id = update.effective_user.id

    await query.answer()

    data = user_results.get(user_id)

    if not data:
        await query.message.reply_text(
            "❌ Результаты поиска устарели."
        )
        return

    tracks = data.get("tracks", [])

    if index < 0 or index >= len(tracks):
        return

    track = tracks[index]

    favorites = user_favorites.setdefault(
        user_id,
        [],
    )

    track_id = track.get("trackId")

    if any(
        item.get("trackId") == track_id
        for item in favorites
    ):
        await query.message.reply_text(
            "❤️ Этот трек уже в твоей музыке."
        )
        return

    favorites.append(track)

    await query.message.reply_text(
        "❤️ Трек добавлен в «Моя музыка»."
    )


# =========================================================
# МОЯ МУЗЫКА
# =========================================================

async def show_favorites(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if query:
        await query.answer()
        user_id = query.from_user.id
        message = query.message
    else:
        user_id = update.effective_user.id
        message = update.message

    favorites = user_favorites.get(
        user_id,
        [],
    )

    if not favorites:
        await message.reply_text(
            "❤️ <b>Моя музыка</b>\n\n"
            "Здесь пока ничего нет.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        return

    buttons = []

    for index, track in enumerate(favorites):
        title = track.get(
            "trackName",
            "Без названия",
        )

        artist = track.get(
            "artistName",
            "Неизвестный исполнитель",
        )

        text = f"🎵 {title} — {artist}"

        if len(text) > 60:
            text = text[:57] + "..."

        buttons.append([
            InlineKeyboardButton(
                text,
                callback_data=f"favplay_{index}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Меню",
            callback_data="menu",
        )
    ])

    await message.reply_text(
        "❤️ <b>Моя музыка</b>\n\n"
        "Твои сохранённые треки:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def play_favorite(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    index: int,
):
    query = update.callback_query
    user_id = update.effective_user.id

    await query.answer()

    favorites = user_favorites.get(
        user_id,
        [],
    )

    if index < 0 or index >= len(favorites):
        await query.message.reply_text(
            "❌ Трек не найден."
        )
        return

    track = favorites[index]

    title = track.get(
        "trackName",
        "Без названия",
    )

    artist = track.get(
        "artistName",
        "Неизвестный исполнитель",
    )

    preview_url = track.get("previewUrl")
    track_url = track.get("trackViewUrl")

    if preview_url:
        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
            ) as client:

                response = await client.get(preview_url)
                response.raise_for_status()

                audio_data = response.content

            await query.message.reply_audio(
                audio=audio_data,
                title=title,
                performer=artist,
                caption=(
                    f"🎵 <b>{html.escape(title)}</b>\n"
                    f"🎤 {html.escape(artist)}\n\n"
                    "▶️ 30-секундное превью"
                ),
                parse_mode="HTML",
            )

            return

        except Exception as error:
            logger.exception(
                "Ошибка избранного: %s",
                error,
            )

    buttons = []

    if track_url:
        buttons.append([
            InlineKeyboardButton(
                "🎵 Открыть трек",
                url=track_url,
            )
        ])

    await query.message.reply_text(
        f"🎵 <b>{html.escape(title)}</b>\n"
        f"🎤 {html.escape(artist)}\n\n"
        "Доступна ссылка на официальный источник.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# =========================================================
# ИСТОЧНИКИ
# =========================================================

async def show_sources(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    soundcloud_status = (
        "🟢 подключён"
        if soundcloud.enabled
        else "⚪ ключи не добавлены"
    )

    text = (
        "<b>⚙️ ИСТОЧНИКИ</b>\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "🍎 Apple Music / iTunes — 🟢 активно\n"
        "🟢 Spotify — подготовлено\n"
        "▶️ YouTube — подготовлено\n"
        f"☁️ SoundCloud — {soundcloud_status}\n\n"
        "SoundCloud включится автоматически, "
        "когда в Railway будут добавлены его API-ключи."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅️ Меню",
                callback_data="menu",
            )
        ]
    ])

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# =========================================================
# ПОМОЩЬ
# =========================================================

async def show_help(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    text = (
        "<b>ℹ️ ПОМОЩЬ</b>\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "🔎 <b>Поиск</b> — найти музыку.\n\n"
        "❤️ <b>Моя музыка</b> — сохранённые треки.\n\n"
        "⚙️ <b>Источники</b> — подключённые музыкальные сервисы.\n\n"
        "🎵 Для Apple Music/iTunes доступны "
        "официальные превью и ссылки.\n\n"
        "☁️ SoundCloud будет подключён через "
        "официальный API после добавления ключей."
    )

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


# =========================================================
# CALLBACK
# =========================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    data = query.data

    if data == "menu":
        await query.answer()

        await query.message.reply_text(
            "🎵 <b>Главное меню</b>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        return

    if data == "search":
        await search_music(update, context)
        return

    if data == "favorites":
        await show_favorites(update, context)
        return

    if data == "sources":
        await show_sources(update, context)
        return

    if data == "help":
        await show_help(update, context)
        return

    if data == "back_results":
        await query.answer()

        user_id = update.effective_user.id
        result = user_results.get(user_id)

        if not result:
            await query.message.reply_text(
                "❌ Результаты поиска устарели.",
                reply_markup=main_menu_keyboard(),
            )
            return

        query_text = result.get("query", "")
        tracks = result.get("tracks", [])

        await query.message.reply_text(
            f"🔎 <b>{html.escape(query_text)}</b>\n\n"
            "👇 Выбери трек:",
            parse_mode="HTML",
            reply_markup=results_keyboard(tracks),
        )
        return

    if data.startswith("play_"):
        try:
            index = int(data.split("_", 1)[1])
        except ValueError:
            return

        await play_track(
            update,
            context,
            index,
        )
        return

    if data.startswith("favplay_"):
        try:
            index = int(data.split("_", 1)[1])
        except ValueError:
            return

        await play_favorite(
            update,
            context,
            index,
        )
        return

    if data.startswith("favorite_"):
        try:
            index = int(data.split("_", 1)[1])
        except ValueError:
            return

        await toggle_favorite(
            update,
            context,
            index,
        )
        return


# =========================================================
# ТЕКСТОВЫЕ СООБЩЕНИЯ
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if context.user_data.get("waiting_for_search"):
        await search_music(
            update,
            context,
        )
        return

    await update.message.reply_text(
        "❓ Используй меню MUSIC BOT.",
        reply_markup=main_menu_keyboard(),
    )


# =========================================================
# MAIN
# =========================================================

def main():
    if not TOKEN:
        raise RuntimeError(
            "Переменная BOT_TOKEN не установлена."
        )

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            callback_handler,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    logger.info("🎵 MUSIC BOT запущен")

    application.run_polling(
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()