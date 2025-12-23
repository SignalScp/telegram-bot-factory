#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot Factory - создает и хостит ботов с ИИ на базе OnlySq API
"""

import asyncio
import logging
import os
import json
from typing import Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

from bot_manager import BotManager
from onlysq_api import OnlySqAPI
from database import Database

# Загрузка переменных окружения
load_dotenv()

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
CREATE_PROMPT, CREATE_NAME, CREATE_TOKEN = range(3)


class BotFactory:
    """Главный класс фабрики ботов"""

    def __init__(self, token: str):
        self.token = token
        self.bot_manager = BotManager()
        self.onlysq = OnlySqAPI()
        self.db = Database('bots.db')
        self.application = None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        welcome_text = (
            f"👋 Привет, {user.mention_html()}!\n\n"
            "🤖 Я - Фабрика Ботов. Создаю и хощу Telegram ботов с ИИ!\n\n"
            "📋 Команды:\n"
            "/create - Создать нового бота\n"
            "/mybots - Список твоих ботов\n"
            "/stop_bot - Остановить бота\n"
            "/delete_bot - Удалить бота\n"
            "/help - Помощь"
        )

        keyboard = [
            [InlineKeyboardButton("🆕 Создать бота", callback_data='create_bot')],
            [InlineKeyboardButton("📋 Мои боты", callback_data='my_bots')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_html(welcome_text, reply_markup=reply_markup)

    async def create_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания бота"""
        query = update.callback_query
        if query:
            await query.answer()
            message = query.message
        else:
            message = update.message

        await message.reply_text(
            "🎨 Отлично! Давай создадим твоего бота.\n\n"
            "Опиши, каким должен быть твой бот. Например:\n"
            "- Дружелюбный помощник для изучения английского\n"
            "- Мрачный детектив-консультант\n"
            "- Веселый мем-генератор\n\n"
            "Или отправь /cancel для отмены."
        )
        return CREATE_PROMPT

    async def create_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение промпта для бота"""
        context.user_data['bot_prompt'] = update.message.text

        await update.message.reply_text(
            "👍 Отлично!\n\n"
            "Теперь придумай имя для бота (например: MyAwesomeBot)\n"
            "Имя должно заканчиваться на 'bot' или 'Bot'"
        )
        return CREATE_NAME

    async def create_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение имени бота"""
        bot_name = update.message.text.strip()

        if not bot_name.lower().endswith('bot'):
            await update.message.reply_text(
                "❌ Имя бота должно заканчиваться на 'bot' или 'Bot'\n"
                "Попробуй еще раз:"
            )
            return CREATE_NAME

        context.user_data['bot_name'] = bot_name

        await update.message.reply_text(
            "🔑 Последний шаг!\n\n"
            "Отправь токен бота от @BotFather\n"
            "(Формат: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)\n\n"
            "Если еще не создал бота, сделай это в @BotFather командой /newbot"
        )
        return CREATE_TOKEN

    async def create_finish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершение создания и запуск бота"""
        bot_token = update.message.text.strip()
        user_id = update.effective_user.id

        # Валидация токена
        if not self._validate_token(bot_token):
            await update.message.reply_text(
                "❌ Неверный формат токена. Попробуй еще раз или /cancel"
            )
            return CREATE_TOKEN

        bot_prompt = context.user_data['bot_prompt']
        bot_name = context.user_data['bot_name']

        await update.message.reply_text(
            "⏳ Создаю и запускаю бота...\n"
            "Это может занять несколько секунд."
        )

        try:
            # Генерируем системный промпт с помощью OnlySq
            system_prompt = await self.onlysq.generate_bot_prompt(bot_prompt)

            # Сохраняем в БД
            bot_id = self.db.create_bot(
                user_id=user_id,
                bot_name=bot_name,
                bot_token=bot_token,
                system_prompt=system_prompt,
                description=bot_prompt
            )

            # Запускаем бота
            success = await self.bot_manager.start_bot(
                bot_id=bot_id,
                bot_token=bot_token,
                system_prompt=system_prompt,
                onlysq_api=self.onlysq
            )

            if success:
                await update.message.reply_text(
                    f"✅ Бот @{bot_name} успешно создан и запущен!\n\n"
                    f"🎯 Описание: {bot_prompt}\n\n"
                    "Можешь начать общаться с ним прямо сейчас!"
                )
            else:
                self.db.delete_bot(bot_id)
                await update.message.reply_text(
                    "❌ Ошибка запуска бота. Проверь токен и попробуй снова."
                )
        except Exception as e:
            logger.error(f"Error creating bot: {e}")
            await update.message.reply_text(
                f"❌ Произошла ошибка: {str(e)}\n\n"
                "Попробуй создать бота заново командой /create"
            )

        context.user_data.clear()
        return ConversationHandler.END

    async def my_bots(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список ботов пользователя"""
        query = update.callback_query
        if query:
            await query.answer()
            message = query.message
        else:
            message = update.message

        user_id = update.effective_user.id
        bots = self.db.get_user_bots(user_id)

        if not bots:
            await message.reply_text(
                "📭 У тебя пока нет ботов.\n\n"
                "Создай первого командой /create"
            )
            return

        text = "🤖 Твои боты:\n\n"
        keyboard = []

        for bot in bots:
            status = "🟢 Активен" if bot['is_active'] else "🔴 Остановлен"
            text += f"@{bot['bot_name']} - {status}\n"
            text += f"   📝 {bot['description']}\n\n"

            keyboard.append([
                InlineKeyboardButton(
                    f"⚙️ {bot['bot_name']}",
                    callback_data=f"manage_{bot['id']}"
                )
            ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(text, reply_markup=reply_markup)

    async def manage_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Управление конкретным ботом"""
        query = update.callback_query
        await query.answer()

        bot_id = int(query.data.split('_')[1])
        bot = self.db.get_bot(bot_id)

        if not bot or bot['user_id'] != update.effective_user.id:
            await query.message.reply_text("❌ Бот не найден")
            return

        keyboard = []
        if bot['is_active']:
            keyboard.append([InlineKeyboardButton(
                "⏸ Остановить",
                callback_data=f"stop_{bot_id}"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                "▶️ Запустить",
                callback_data=f"start_{bot_id}"
            )])

        keyboard.append([InlineKeyboardButton(
            "🗑 Удалить",
            callback_data=f"delete_{bot_id}"
        )])
        keyboard.append([InlineKeyboardButton(
            "◀️ Назад",
            callback_data="my_bots"
        )])

        reply_markup = InlineKeyboardMarkup(keyboard)

        status = "🟢 Активен" if bot['is_active'] else "🔴 Остановлен"
        await query.message.edit_text(
            f"⚙️ Управление ботом @{bot['bot_name']}\n\n"
            f"Статус: {status}\n"
            f"📝 Описание: {bot['description']}\n"
            f"📅 Создан: {bot['created_at']}",
            reply_markup=reply_markup
        )

    async def stop_bot_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Остановить бота"""
        query = update.callback_query
        await query.answer()

        bot_id = int(query.data.split('_')[1])
        bot = self.db.get_bot(bot_id)

        if not bot or bot['user_id'] != update.effective_user.id:
            await query.message.reply_text("❌ Бот не найден")
            return

        await self.bot_manager.stop_bot(bot_id)
        self.db.update_bot_status(bot_id, False)

        await query.message.reply_text(
            f"⏸ Бот @{bot['bot_name']} остановлен"
        )

    async def start_bot_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запустить бота"""
        query = update.callback_query
        await query.answer()

        bot_id = int(query.data.split('_')[1])
        bot = self.db.get_bot(bot_id)

        if not bot or bot['user_id'] != update.effective_user.id:
            await query.message.reply_text("❌ Бот не найден")
            return

        success = await self.bot_manager.start_bot(
            bot_id=bot_id,
            bot_token=bot['bot_token'],
            system_prompt=bot['system_prompt'],
            onlysq_api=self.onlysq
        )

        if success:
            self.db.update_bot_status(bot_id, True)
            await query.message.reply_text(
                f"▶️ Бот @{bot['bot_name']} запущен"
            )
        else:
            await query.message.reply_text(
                f"❌ Ошибка запуска бота @{bot['bot_name']}"
            )

    async def delete_bot_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удалить бота"""
        query = update.callback_query
        await query.answer()

        bot_id = int(query.data.split('_')[1])
        bot = self.db.get_bot(bot_id)

        if not bot or bot['user_id'] != update.effective_user.id:
            await query.message.reply_text("❌ Бот не найден")
            return

        await self.bot_manager.stop_bot(bot_id)
        self.db.delete_bot(bot_id)

        await query.message.reply_text(
            f"🗑 Бот @{bot['bot_name']} удален"
        )

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания бота"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Создание бота отменено.\n\n"
            "Используй /create чтобы начать заново."
        )
        return ConversationHandler.END

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда помощи"""
        help_text = (
            "📚 *Справка по Фабрике Ботов*\n\n"
            "*Создание бота:*\n"
            "1️⃣ /create - начать создание\n"
            "2️⃣ Опиши характер и функции бота\n"
            "3️⃣ Придумай имя (должно заканчиваться на bot)\n"
            "4️⃣ Создай бота в @BotFather и отправь токен\n\n"
            "*Управление:*\n"
            "/mybots - список твоих ботов\n"
            "/stop_bot - остановить бота\n"
            "/delete_bot - удалить бота\n\n"
            "*Особенности:*\n"
            "• Боты работают на базе OnlySq API\n"
            "• Бесплатно и без ограничений\n"
            "• Боты работают 24/7 на нашем хостинге\n"
            "• Можешь создать несколько ботов\n\n"
            "По вопросам: @yourusername"
        )
        await update.message.reply_markdown(help_text)

    @staticmethod
    def _validate_token(token: str) -> bool:
        """Базовая валидация токена"""
        parts = token.split(':')
        if len(parts) != 2:
            return False
        return parts[0].isdigit() and len(parts[1]) > 20

    def run(self):
        """Запуск фабрики"""
        self.application = Application.builder().token(self.token).build()

        # ConversationHandler для создания бота
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('create', self.create_start),
                CallbackQueryHandler(self.create_start, pattern='^create_bot$')
            ],
            states={
                CREATE_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.create_prompt)],
                CREATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.create_name)],
                CREATE_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.create_finish)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )

        # Handlers
        self.application.add_handler(CommandHandler('start', self.start))
        self.application.add_handler(conv_handler)
        self.application.add_handler(CommandHandler('mybots', self.my_bots))
        self.application.add_handler(CommandHandler('help', self.help_command))

        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.my_bots, pattern='^my_bots$'))
        self.application.add_handler(CallbackQueryHandler(self.manage_bot, pattern='^manage_'))
        self.application.add_handler(CallbackQueryHandler(self.stop_bot_callback, pattern='^stop_'))
        self.application.add_handler(CallbackQueryHandler(self.start_bot_callback, pattern='^start_'))
        self.application.add_handler(CallbackQueryHandler(self.delete_bot_callback, pattern='^delete_'))

        logger.info("🚀 Bot Factory запущена!")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    TOKEN = os.getenv('FACTORY_BOT_TOKEN')
    if not TOKEN:
        logger.error("❌ Не указан FACTORY_BOT_TOKEN в .env")
        exit(1)

    factory = BotFactory(TOKEN)
    factory.run()
