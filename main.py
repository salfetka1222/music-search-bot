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
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

API_URL = "https://itunes.apple.com/search"


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyboard = [
        [
            InlineKeyboardButton(
                "🎵 Как искать музыку",
                callback_data="help",
            )
        ]
    ]

    await update.message.reply_text(
        "🎧 Music Search Bot\n\n"
        "Я помогу тебе найти музыку!\n\n"
        "🔎 Отправь название песни "
        "или имя исполнителя.\n\n"
        "Например: The Weeknd Blinding Lights",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "🔎 Просто отправь мне название песни "
        "или имя исполнителя.\n\n"
        "Например:\n"
        "• Imagine Dragons\n"
        "• Believer\n"
        "• The Weeknd Blinding Lights"
    )


async def search_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.message.text:
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
        "🔎 Ищу музыку..."
    )

    params = {
        "term": search_query,
        "media": "music",
        "entity": "song",
        "limit": 10,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                API_URL,
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        tracks = data.get("results", [])

        if not tracks:
            await status.edit_text(
                "😕 Ничего не найдено.\n"
                "Попробуй другой запрос."
            )
            return

        await status.edit_text(
            f"🎵 Результаты поиска: {search_query}"
        )

        for track in tracks:
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
            artwork = track.get("artworkUrl100")
            preview = track.get("previewUrl")
            track_url = track.get("trackViewUrl")

            text = (
                f"🎵 {title}\n"
                f"👤 Исполнитель: {artist}\n"
                f"💿 Альбом: {album}"
            )

            buttons = []

            if preview:
                buttons.append(
                    InlineKeyboardButton(
                        "▶️ Слушать превью",
                        url=preview,
                    )
                )

            if track_url:
                buttons.append(
                    InlineKeyboardButton(
                        "🍎 Открыть трек",
                        url=track_url,
                    )
                )

            markup = (
                InlineKeyboardMarkup([buttons])
                if buttons
                else None
            )

            if artwork:
                await update.message.reply_photo(
                    photo=artwork,
                    caption=text,
                    reply_markup=markup,
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=markup,
                )

    except httpx.TimeoutException:
        await status.edit_text(
            "⏳ Поиск занял слишком много времени. "
            "Попробуй ещё раз."
        )

    except httpx.HTTPError:
        logging.exception("Ошибка музыкального API")

        await status.edit_text(
            "⚠️ Не удалось подключиться к поиску музыки."
        )

    except Exception:
        logging.exception("Неожиданная ошибка")

        await status.edit_text(
            "⚠️ Произошла ошибка. Попробуй позже."
        )


def main():
    if not TOKEN:
        raise RuntimeError(
            "Не задана переменная окружения BOT_TOKEN"
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search_music,
        )
    )

    app.run_polling()


if __name__ == "__main__":
    main()