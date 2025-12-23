#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер для управления запущенными ботами
"""

import asyncio
import logging
from typing import Dict, Optional
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from onlysq_api import OnlySqAPI

logger = logging.getLogger(__name__)


class ManagedBot:
    """Класс для управляемого бота"""

    def __init__(self, bot_id: int, bot_token: str, system_prompt: str, onlysq_api: OnlySqAPI):
        self.bot_id = bot_id
        self.bot_token = bot_token
        self.system_prompt = system_prompt
        self.onlysq = onlysq_api
        self.application: Optional[Application] = None
        self.task: Optional[asyncio.Task] = None
        self.user_contexts: Dict[int, list] = {}  # user_id -> message history

    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /start для управляемого бота"""
        user_id = update.effective_user.id
        self.user_contexts[user_id] = []

        await update.message.reply_text(
            "👋 Привет! Я готов к общению. Напиши мне что-нибудь!"
        )

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик сообщений для управляемого бота"""
        user_id = update.effective_user.id
        user_message = update.message.text

        # Инициализация контекста пользователя
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []

        # Добавляем сообщение пользователя
        self.user_contexts[user_id].append({
            "role": "user",
            "content": user_message
        })

        # Ограничение истории (последние 10 сообщений)
        if len(self.user_contexts[user_id]) > 20:
            self.user_contexts[user_id] = self.user_contexts[user_id][-20:]

        try:
            # Отправка запроса в OnlySq API
            response = await self.onlysq.chat(
                messages=self.user_contexts[user_id],
                system_prompt=self.system_prompt
            )

            # Добавляем ответ в историю
            self.user_contexts[user_id].append({
                "role": "assistant",
                "content": response
            })

            await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Error in bot {self.bot_id}: {e}")
            await update.message.reply_text(
                "😔 Извини, произошла ошибка. Попробуй еще раз."
            )

    async def reset_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сброс контекста диалога"""
        user_id = update.effective_user.id
        self.user_contexts[user_id] = []
        await update.message.reply_text(
            "🔄 Контекст диалога сброшен. Начнем с чистого листа!"
        )

    async def start_polling(self):
        """Запуск бота в режиме polling"""
        self.application = Application.builder().token(self.bot_token).build()

        # Добавление handlers
        self.application.add_handler(CommandHandler('start', self.start_handler))
        self.application.add_handler(CommandHandler('reset', self.reset_handler))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler)
        )

        # Запуск в отдельной задаче
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        logger.info(f"✅ Bot {self.bot_id} started")

    async def stop(self):
        """Остановка бота"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info(f"⏸ Bot {self.bot_id} stopped")


class BotManager:
    """Менеджер для управления множеством ботов"""

    def __init__(self):
        self.bots: Dict[int, ManagedBot] = {}

    async def start_bot(
        self,
        bot_id: int,
        bot_token: str,
        system_prompt: str,
        onlysq_api: OnlySqAPI
    ) -> bool:
        """Запустить нового бота"""
        try:
            if bot_id in self.bots:
                logger.warning(f"Bot {bot_id} already running")
                return False

            managed_bot = ManagedBot(bot_id, bot_token, system_prompt, onlysq_api)
            await managed_bot.start_polling()

            self.bots[bot_id] = managed_bot
            return True

        except Exception as e:
            logger.error(f"Failed to start bot {bot_id}: {e}")
            return False

    async def stop_bot(self, bot_id: int) -> bool:
        """Остановить бота"""
        if bot_id not in self.bots:
            logger.warning(f"Bot {bot_id} not found")
            return False

        try:
            await self.bots[bot_id].stop()
            del self.bots[bot_id]
            return True
        except Exception as e:
            logger.error(f"Failed to stop bot {bot_id}: {e}")
            return False

    async def stop_all(self):
        """Остановить всех ботов"""
        for bot_id in list(self.bots.keys()):
            await self.stop_bot(bot_id)

    def get_running_bots(self) -> list:
        """Получить список запущенных ботов"""
        return list(self.bots.keys())
