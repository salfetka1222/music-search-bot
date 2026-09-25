import os
import logging
import httpx

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://itunes.apple.com/search"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ============================================================
# ХРАНИЛИЩЕ
# ============================================================

# Результаты поиска пользователей
user_results = {}

# Избранное пользователей
user_favorites = {}


# ============================================================
# КЛАВИАТУРЫ
# ============================================================

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔎 Поиск",
                callback_data="search",
            ),
            InlineKeyboardButton(
                "❤️ Моя музыка",
                callback_data="favorites",
            ),
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Помощь",
                callback_data="help",
            ),
        ],
    ])


def results_keyboard(tracks):
    keyboard = []

    for index, track in enumerate(tracks):
        title = track.get(
            "trackName",
            "Неизвестный трек",
        )

        artist = track.get(
            "artistName",
            "Неизвестный исполнитель",
        )

        # Ограничиваем длину кнопки,
        # чтобы Telegram не получал слишком длинный текст.
        button_text = f"🎵 {title} — {artist}"

        if len(button_text) > 55:
            button_text = button_text[:52] + "..."

        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"play_{index}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔄 Новый поиск",
            callback_data="search",
        ),
        InlineKeyboardButton(
            "❤️ Моя музыка",
            callback_data="favorites",
        ),
    ])

    keyboard.append([
        InlineKeyboardButton(
            "🏠 Меню",
            callback_data="menu",
        )
    ])

    return InlineKeyboardMarkup(keyboard)


def track_keyboard(index, favorite=False):
    favorite_text = (
        "💔 Убрать из избранного"
        if favorite
        else "❤️ В избранное"
    )

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "▶️ Слушать",
                callback_data=f"play_{index}",
            ),
        ],
        [
            InlineKeyboardButton(
                favorite_text,
                callback_data=f"favorite_{index}",
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад к результатам",
                callback_data="back_results",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔎 Новый поиск",
                callback_data="search",
            ),
            InlineKeyboardButton(
                "🏠 Меню",
                callback_data="menu",
            ),
        ],
    ])


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    if user_id not in user_favorites:
        user_favorites[user_id] = []

    text = (
        "🎵 <b>MUSIC BOT</b>\n\n"
        "🔎 <b>Поиск музыки</b>\n"
        "Найди песню по названию или исполнителю.\n\n"
        "Примеры:\n"
        "• The Weeknd\n"
        "• Blinding Lights\n"
        "• dabbackwood старые фотографии\n\n"
        "Выбери действие ниже:"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


# ============================================================
# ПОИСК
# ============================================================

async def search_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    search_query = update.message.text.strip()

    if len(search_query) < 2:
        await update.message.reply_text(
            "❌ Введи название песни или исполнителя."
        )
        return

    if len(search_query) > 200:
        await update.message.reply_text(
            "❌ Запрос слишком длинный."
        )
        return

    status = await update.message.reply_text(
        "🔎 <b>Ищу музыку...</b>",
        parse_mode="HTML",
    )

    params = {
        "term": search_query,
        "media": "music",
        "entity": "song",
        "limit": 10,
    }

    try:
        async with httpx.AsyncClient(
            timeout=15
        ) as client:
            response = await client.get(
                API_URL,
                params=params,
            )

            response.raise_for_status()

            data = response.json()

        tracks = data.get("results", [])

        if not tracks:
            await status.edit_text(
                "😕 <b>Ничего не найдено</b>\n\n"
                "Попробуй изменить запрос.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🔎 Новый поиск",
                            callback_data="search",
                        ),
                        InlineKeyboardButton(
                            "🏠 Меню",
                            callback_data="menu",
                        ),
                    ]
                ]),
            )
            return

        user_id = update.effective_user.id

        user_results[user_id] = {
            "query": search_query,
            "tracks": tracks,
        }

        text = (
            "🎵 <b>MUSIC BOT</b>\n\n"
            f"🔎 <b>Поиск:</b> "
            f"<i>{search_query}</i>\n\n"
            "━━━━━━━━━━━━━━━━\n\n"
        )

        for index, track in enumerate(tracks):
            title = track.get(
                "trackName",
                "Неизвестный трек",
            )

            artist = track.get(
                "artistName",
                "Неизвестный исполнитель",
            )

            text += (
                f"<b>{index + 1}.</b> "
                f"{title} — {artist}\n"
            )

        text += (
            "\n━━━━━━━━━━━━━━━━\n\n"
            "👇 <b>Выбери трек:</b>"
        )

        await status.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=results_keyboard(tracks),
            disable_web_page_preview=True,
        )

    except httpx.TimeoutException:
        await status.edit_text(
            "⏳ Поиск занял слишком много времени.\n"
            "Попробуй ещё раз."
        )

    except httpx.HTTPError:
        logging.exception("Ошибка API")

        await status.edit_text(
            "⚠️ Не удалось подключиться "
            "к музыкальному поиску."
        )

    except Exception:
        logging.exception("Неожиданная ошибка")

        await status.edit_text(
            "⚠️ Произошла ошибка.\n"
            "Попробуй ещё раз."
        )


# ============================================================
# ПРОСМОТР ТРЕКА
# ============================================================

async def show_track(
    query,
    index,
):
    user_id = query.from_user.id

    data = user_results.get(user_id)

    if not data:
        await query.message.reply_text(
            "❌ Результаты поиска больше недоступны.\n"
            "Сделай новый поиск."
        )
        return

    tracks = data["tracks"]

    if index < 0 or index >= len(tracks):
        await query.message.reply_text(
            "❌ Трек не найден."
        )
        return

    track = tracks[index]

    title = track.get(
        "trackName",
        "Неизвестный трек",
    )

    artist = track.get(
        "artistName",
        "Неизвестный исполнитель",
    )

    album = track.get(
        "collectionName",
        "Неизвестный альбом",
    )

    track_url = track.get(
        "trackViewUrl"
    )

    favorites = user_favorites.setdefault(
        user_id,
        [],
    )

    is_favorite = any(
        item.get("trackId") == track.get("trackId")
        for item in favorites
    )

    text = (
        "🎵 <b>ТРЕК</b>\n\n"
        f"🎧 <b>{title}</b>\n"
        f"👤 {artist}\n"
        f"💿 {album}\n\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "▶️ Нажми «Слушать», чтобы "
        "получить доступное аудио-превью."
    )

    buttons = [
        [
            InlineKeyboardButton(
                "▶️ Слушать",
                callback_data=f"audio_{index}",
            ),
        ],
        [
            InlineKeyboardButton(
                (
                    "💔 Убрать из избранного"
                    if is_favorite
                    else "❤️ В избранное"
                ),
                callback_data=f"favorite_{index}",
            ),
        ],
    ]

    if track_url:
        buttons.append([
            InlineKeyboardButton(
                "🔗 Открыть официальный источник",
                url=track_url,
            )
        ])

    buttons.extend([
        [
            InlineKeyboardButton(
                "⬅️ Назад к результатам",
                callback_data="back_results",
            )
        ],
        [
            InlineKeyboardButton(
                "🔎 Новый поиск",
                callback_data="search",
            ),
            InlineKeyboardButton(
                "🏠 Меню",
                callback_data="menu",
            ),
        ],
    ])

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )


# ============================================================
# АУДИО-ПРЕВЬЮ
# ============================================================

async def send_audio(
    query,
    index,
):
    user_id = query.from_user.id

    data = user_results.get(user_id)

    if not data:
        await query.message.reply_text(
            "❌ Результаты поиска устарели.\n"
            "Сделай новый поиск."
        )
        return

    tracks = data["tracks"]

    if index < 0 or index >= len(tracks):
        await query.message.reply_text(
            "❌ Трек не найден."
        )
        return

    track = tracks[index]

    title = track.get(
        "trackName",
        "Неизвестный трек",
    )

    artist = track.get(
        "artistName",
        "Неизвестный исполнитель",
    )

    preview_url = track.get(
        "previewUrl"
    )

    if not preview_url:
        await query.message.reply_text(
            "❌ Для этого трека нет "
            "доступного аудио-превью."
        )
        return

    await query.answer(
        "🎵 Загружаю аудио..."
    )

    try:
        async with httpx.AsyncClient(
            timeout=30
        ) as client:
            response = await client.get(
                preview_url
            )

            response.raise_for_status()

            audio_data = response.content

        await query.message.reply_audio(
            audio=audio_data,
            title=title,
            performer=artist,
            caption=(
                f"🎵 <b>{title}</b>\n"
                f"👤 {artist}\n\n"
                "▶️ Аудио-превью"
            ),
            parse_mode="HTML",
        )

    except Exception:
        logging.exception(
            "Ошибка отправки аудио"
        )

        await query.message.reply_text(
            "⚠️ Не удалось отправить аудио."
        )


# ============================================================
# ИЗБРАННОЕ
# ============================================================

async def toggle_favorite(
    query,
    index,
):
    user_id = query.from_user.id

    data = user_results.get(user_id)

    if not data:
        await query.answer(
            "❌ Результаты устарели."
        )
        return

    tracks = data["tracks"]

    if index < 0 or index >= len(tracks):
        await query.answer(
            "❌ Трек не найден."
        )
        return

    track = tracks[index]

    favorites = user_favorites.setdefault(
        user_id,
        [],
    )

    track_id = track.get("trackId")

    existing = next(
        (
            item
            for item in favorites
            if item.get("trackId") == track_id
        ),
        None,
    )

    if existing:
        favorites.remove(existing)

        await query.answer(
            "💔 Убрано из избранного"
        )
    else:
        favorites.append(track)

        await query.answer(
            "❤️ Добавлено в избранное"
        )

    await show_track(
        query,
        index,
    )


async def show_favorites(
    query,
):
    user_id = query.from_user.id

    favorites = user_favorites.get(
        user_id,
        [],
    )

    if not favorites:
        await query.message.reply_text(
            "❤️ <b>Моя музыка</b>\n\n"
            "Тут пока ничего нет.\n\n"
            "Открой поиск и добавь понравившиеся "
            "треки в избранное.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔎 Найти музыку",
                        callback_data="search",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 Меню",
                        callback_data="menu",
                    )
                ],
            ]),
        )
        return

    text = (
        "❤️ <b>МОЯ МУЗЫКА</b>\n\n"
        "Твои сохранённые треки:\n\n"
        "━━━━━━━━━━━━━━━━\n\n"
    )

    keyboard = []

    for index, track in enumerate(favorites):
        title = track.get(
            "trackName",
            "Неизвестный трек",
        )

        artist = track.get(
            "artistName",
            "Неизвестный исполнитель",
        )

        text += (
            f"<b>{index + 1}.</b> "
            f"{title} — {artist}\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"🎵 {title} — {artist}",
                callback_data=f"favplay_{index}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔎 Поиск",
            callback_data="search",
        ),
        InlineKeyboardButton(
            "🏠 Меню",
            callback_data="menu",
        ),
    ])

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        disable_web_page_preview=True,
    )


async def play_favorite(
    query,
    index,
):
    user_id = query.from_user.id

    favorites = user_favorites.get(
        user_id,
        [],
    )

    if index < 0 or index >= len(favorites):
        await query.answer(
            "❌ Трек не найден."
        )
        return

    track = favorites[index]

    preview_url = track.get(
        "previewUrl"
    )

    title = track.get(
        "trackName",
        "Неизвестный трек",
    )

    artist = track.get(
        "artistName",
        "Неизвестный исполнитель",
    )

    if not preview_url:
        await query.answer(
            "❌ Для этого трека нет превью."
        )
        return

    await query.answer(
        "🎵 Загружаю..."
    )

    try:
        async with httpx.AsyncClient(
            timeout=30
        ) as client:
            response = await client.get(
                preview_url
            )

            response.raise_for_status()

            audio_data = response.content

        await query.message.reply_audio(
            audio=audio_data,
            title=title,
            performer=artist,
            caption=(
                f"🎵 <b>{title}</b>\n"
                f"👤 {artist}"
            ),
            parse_mode="HTML",
        )

    except Exception:
        logging.exception(
            "Ошибка избранного аудио"
        )

        await query.message.reply_text(
            "⚠️ Не удалось загрузить аудио."
        )


# ============================================================
# МЕНЮ
# ============================================================

async def show_menu(
    query,
):
    await query.message.reply_text(
        "🎵 <b>MUSIC BOT</b>\n\n"
        "Добро пожаловать!\n\n"
        "🔎 Найди музыку\n"
        "❤️ Сохраняй любимые треки\n"
        "🎧 Слушай доступные превью\n\n"
        "Выбери действие:",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def show_help(
    query,
):
    await query.message.reply_text(
        "ℹ️ <b>Как пользоваться</b>\n\n"
        "1️⃣ Нажми «🔎 Поиск».\n"
        "2️⃣ Отправь название песни "
        "или исполнителя.\n"
        "3️⃣ Выбери нужный трек.\n"
        "4️⃣ Нажми «▶️ Слушать».\n\n"
        "Также можно сохранять треки "
        "в «❤️ Моя музыка».",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔎 Поиск",
                    callback_data="search",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Меню",
                    callback_data="menu",
                )
            ],
        ]),
    )


# ============================================================
# CALLBACK
# ============================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    data = query.data

    try:
        if data == "menu":
            await query.answer()
            await show_menu(query)

        elif data == "search":
            await query.answer()

            await query.message.reply_text(
                "🔎 <b>Поиск музыки</b>\n\n"
                "Отправь название песни "
                "или имя исполнителя.",
                parse_mode="HTML",
            )

        elif data == "help":
            await query.answer()
            await show_help(query)

        elif data == "favorites":
            await query.answer()
            await show_favorites(query)

        elif data == "back_results":
            await query.answer()

            user_id = query.from_user.id

            result = user_results.get(
                user_id
            )

            if not result:
                await query.message.reply_text(
                    "❌ Результаты поиска "
                    "больше недоступны."
                )
                return

            tracks = result["tracks"]
            search_query = result["query"]

            text = (
                "🎵 <b>MUSIC BOT</b>\n\n"
                f"🔎 <b>Поиск:</b> "
                f"<i>{search_query}</i>\n\n"
                "━━━━━━━━━━━━━━━━\n\n"
            )

            for index, track in enumerate(tracks):
                title = track.get(
                    "trackName",
                    "Неизвестный трек",
                )

                artist = track.get(
                    "artistName",
                    "Неизвестный исполнитель",
                )

                text += (
                    f"<b>{index + 1}.</b> "
                    f"{title} — {artist}\n"
                )

            text += (
                "\n━━━━━━━━━━━━━━━━\n\n"
                "👇 <b>Выбери трек:</b>"
            )

            await query.message.reply_text(
                text,
                parse_mode="HTML",
                reply_markup=results_keyboard(
                    tracks
                ),
                disable_web_page_preview=True,
            )

        elif data.startswith("play_"):
            await query.answer()

            index = int(
                data.replace(
                    "play_",
                    "",
                )
            )

            await show_track(
                query,
                index,
            )

        elif data.startswith("audio_"):
            index = int(
                data.replace(
                    "audio_",
                    "",
                )
            )

            await send_audio(
                query,
                index,
            )

        elif data.startswith("favorite_"):
            index = int(
                data.replace(
                    "favorite_",
                    "",
                )
            )

            await toggle_favorite(
                query,
                index,
            )

        elif data.startswith("favplay_"):
            index = int(
                data.replace(
                    "favplay_",
                    "",
                )
            )

            await play_favorite(
                query,
                index,
            )

    except Exception:
        logging.exception(
            "Ошибка callback"
        )

        try:
            await query.answer(
                "⚠️ Произошла ошибка.",
                show_alert=True,
            )
        except Exception:
            pass


# ============================================================
# ЗАПУСК
# ============================================================

def main():
    if not TOKEN:
        raise RuntimeError(
            "Не задана переменная окружения BOT_TOKEN"
        )

    app = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            search_music,
        )
    )

    app.run_polling()


if __name__ == "__main__":
    main()