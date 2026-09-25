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
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ============================================================
# НАСТРОЙКИ
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")

API_URL = "https://itunes.apple.com/search"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Результаты поиска пользователей
user_results = {}

# Избранное
user_favorites = {}


# ============================================================
# ОСНОВНОЕ МЕНЮ
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


# ============================================================
# КНОПКИ РЕЗУЛЬТАТОВ
# ============================================================

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

        button_text = f"🎵 {title} — {artist}"

        # Telegram ограничивает callback_data,
        # поэтому передаём только номер результата.
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
            "🔎 Новый поиск",
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


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    user_favorites.setdefault(
        user_id,
        [],
    )

    text = (
        "🎵 <b>MUSIC BOT</b>\n\n"
        "🔎 <b>Поиск музыки</b>\n\n"
        "Отправь название песни или исполнителя.\n\n"
        "Например:\n"
        "• The Weeknd\n"
        "• Blinding Lights\n"
        "• dabbackwood\n"
        "• Моя Мишель\n"
        "• MACAN\n"
        "• Miyagi\n\n"
        "Выбери действие:"
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

    # ========================================================
    # ВАЖНО:
    # country=RU помогает искать русскую музыку.
    # lang=ru_ru задаёт русский язык каталога.
    # ========================================================

    params = {
        "term": search_query,
        "media": "music",
        "entity": "song",
        "country": "RU",
        "lang": "ru_ru",
        "limit": 10,
    }

    try:
        async with httpx.AsyncClient(
            timeout=20
        ) as client:

            response = await client.get(
                API_URL,
                params=params,
            )

            response.raise_for_status()

            data = response.json()

        tracks = data.get(
            "results",
            [],
        )

        # ====================================================
        # ЕСЛИ В РОССИЙСКОМ КАТАЛОГЕ НИЧЕГО НЕТ,
        # ДЕЛАЕМ ВТОРОЙ ПОИСК БЕЗ COUNTRY,
        # ЧТОБЫ НЕ ТЕРЯТЬ РЕДКИЕ ТРЕКИ.
        # ====================================================

        if not tracks:
            fallback_params = {
                "term": search_query,
                "media": "music",
                "entity": "song",
                "lang": "ru_ru",
                "limit": 10,
            }

            async with httpx.AsyncClient(
                timeout=20
            ) as client:

                fallback_response = await client.get(
                    API_URL,
                    params=fallback_params,
                )

                fallback_response.raise_for_status()

                fallback_data = (
                    fallback_response.json()
                )

            tracks = fallback_data.get(
                "results",
                [],
            )

        # ====================================================
        # НИЧЕГО НЕ НАЙДЕНО
        # ====================================================

        if not tracks:
            await status.edit_text(
                "😕 <b>Ничего не найдено</b>\n\n"
                f"🔎 Запрос: "
                f"<i>{html.escape(search_query)}</i>\n\n"
                "Попробуй написать название "
                "песни или исполнителя по-другому.",
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

        # Сохраняем результаты
        user_results[user_id] = {
            "query": search_query,
            "tracks": tracks,
        }

        # ====================================================
        # ТЕПЕРЬ ЗДЕСЬ НЕТ СПИСКА 1,2,3...
        # ОСТАЮТСЯ ТОЛЬКО КНОПКИ.
        # ====================================================

        text = (
            "🎵 <b>MUSIC BOT</b>\n\n"
            f"🔎 <b>Поиск:</b> "
            f"<i>{html.escape(search_query)}</i>\n\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "👇 <b>Выбери трек:</b>"
        )

        await status.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=results_keyboard(
                tracks
            ),
            disable_web_page_preview=True,
        )

    except httpx.TimeoutException:

        await status.edit_text(
            "⏳ Поиск занял слишком много времени.\n\n"
            "Попробуй ещё раз."
        )

    except httpx.HTTPError:

        logging.exception(
            "Ошибка музыкального API"
        )

        await status.edit_text(
            "⚠️ Не удалось подключиться "
            "к музыкальному поиску."
        )

    except Exception:

        logging.exception(
            "Неожиданная ошибка поиска"
        )

        await status.edit_text(
            "⚠️ Произошла ошибка.\n\n"
            "Попробуй ещё раз."
        )


# ============================================================
# ВОСПРОИЗВЕДЕНИЕ ТРЕКА
# ============================================================

async def play_track(
    query,
    index,
):
    user_id = query.from_user.id

    data = user_results.get(
        user_id
    )

    if not data:
        await query.answer(
            "❌ Результаты устарели.",
            show_alert=True,
        )
        return

    tracks = data.get(
        "tracks",
        [],
    )

    if index < 0 or index >= len(tracks):
        await query.answer(
            "❌ Трек не найден.",
            show_alert=True,
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

    # ========================================================
    # НЕТ ПРЕВЬЮ
    # ========================================================

    if not preview_url:

        await query.answer(
            "❌ Для этого трека нет доступного превью.",
            show_alert=True,
        )

        track_url = track.get(
            "trackViewUrl"
        )

        if track_url:

            await query.message.reply_text(
                (
                    f"🎵 <b>{html.escape(title)}</b>\n"
                    f"👤 {html.escape(artist)}\n\n"
                    "Для этого трека нет доступного "
                    "аудио-превью."
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🔗 Открыть официальный источник",
                            url=track_url,
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅️ К результатам",
                            callback_data="back_results",
                        )
                    ],
                ]),
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
                f"🎵 <b>{html.escape(title)}</b>\n"
                f"👤 {html.escape(artist)}\n\n"
                "▶️ Аудио-превью"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❤️ В избранное",
                        callback_data=f"favorite_{index}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔎 К результатам",
                        callback_data="back_results",
                    )
                ],
            ]),
        )

    except httpx.HTTPError:

        logging.exception(
            "Ошибка загрузки аудио"
        )

        await query.message.reply_text(
            "⚠️ Не удалось загрузить аудио-превью."
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

    data = user_results.get(
        user_id
    )

    if not data:
        await query.answer(
            "❌ Результаты устарели.",
            show_alert=True,
        )
        return

    tracks = data.get(
        "tracks",
        [],
    )

    if index < 0 or index >= len(tracks):
        await query.answer(
            "❌ Трек не найден.",
            show_alert=True,
        )
        return

    track = tracks[index]

    favorites = user_favorites.setdefault(
        user_id,
        [],
    )

    track_id = track.get(
        "trackId"
    )

    existing = next(
        (
            item
            for item in favorites
            if item.get("trackId") == track_id
        ),
        None,
    )

    if existing:

        favorites.remove(
            existing
        )

        await query.answer(
            "💔 Убрано из избранного"
        )

    else:

        favorites.append(
            track
        )

        await query.answer(
            "❤️ Добавлено в избранное"
        )


# ============================================================
# МОЯ МУЗЫКА
# ============================================================

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
            "Здесь пока ничего нет.\n\n"
            "Найди музыку и добавь понравившиеся "
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
        "👇 Выбери трек:"
    )

    keyboard = []

    for index, track in enumerate(
        favorites
    ):

        title = track.get(
            "trackName",
            "Неизвестный трек",
        )

        artist = track.get(
            "artistName",
            "Неизвестный исполнитель",
        )

        button_text = (
            f"🎵 {title} — {artist}"
        )

        if len(button_text) > 55:
            button_text = (
                button_text[:52] + "..."
            )

        keyboard.append([
            InlineKeyboardButton(
                button_text,
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
            "❌ Трек не найден.",
            show_alert=True,
        )

        return

    track = favorites[index]

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

        await query.answer(
            "❌ Для этого трека нет превью.",
            show_alert=True,
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
                f"🎵 <b>{html.escape(title)}</b>\n"
                f"👤 {html.escape(artist)}"
            ),
            parse_mode="HTML",
        )

    except Exception:

        logging.exception(
            "Ошибка избранного"
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
        "🔎 Поиск музыки\n"
        "❤️ Моя музыка\n"
        "🎧 Аудио-превью\n\n"
        "Выбери действие:",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


async def show_help(
    query,
):
    await query.message.reply_text(
        "ℹ️ <b>Как пользоваться</b>\n\n"
        "🔎 Отправь название песни "
        "или имя исполнителя.\n\n"
        "🎵 Нажми на найденный трек — "
        "бот сразу отправит доступное "
        "аудио-превью.\n\n"
        "❤️ Понравившийся трек можно "
        "добавить в «Моя музыка».",
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

        # ----------------------------------------------------
        # МЕНЮ
        # ----------------------------------------------------

        if data == "menu":

            await query.answer()

            await show_menu(
                query
            )

        # ----------------------------------------------------
        # ПОИСК
        # ----------------------------------------------------

        elif data == "search":

            await query.answer()

            await query.message.reply_text(
                "🔎 <b>Поиск музыки</b>\n\n"
                "Отправь название песни "
                "или имя исполнителя.",
                parse_mode="HTML",
            )

        # ----------------------------------------------------
        # ПОМОЩЬ
        # ----------------------------------------------------

        elif data == "help":

            await query.answer()

            await show_help(
                query
            )

        # ----------------------------------------------------
        # ИЗБРАННОЕ
        # ----------------------------------------------------

        elif data == "favorites":

            await query.answer()

            await show_favorites(
                query
            )

        # ----------------------------------------------------
        # ТРЕК
        # ----------------------------------------------------

        elif data.startswith("play_"):

            index = int(
                data.replace(
                    "play_",
                    "",
                )
            )

            # Сразу отправляем аудио.
            # Никакой промежуточной карточки.
            await play_track(
                query,
                index,
            )

        # ----------------------------------------------------
        # ИЗБРАННОЕ: PLAY
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # ДОБАВИТЬ В ИЗБРАННОЕ
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # НАЗАД К РЕЗУЛЬТАТАМ
        # ----------------------------------------------------

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
                f"<i>{html.escape(search_query)}</i>\n\n"
                "━━━━━━━━━━━━━━━━\n\n"
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