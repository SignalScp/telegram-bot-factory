#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Клиент для работы с OnlySq API
"""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class OnlySqAPI:
    """Клиент для OnlySq API"""

    BASE_URL = "https://api.onlysq.ru/ai/openai"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать сессию"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = "",
        model: str = "gpt-4o-mini",
        temperature: float = 0.7
    ) -> str:
        """
        Отправить запрос в чат API

        Args:
            messages: Список сообщений в формате [{"role": "user", "content": "text"}, ...]
            system_prompt: Системный промпт
            model: Модель для использования
            temperature: Температура генерации (0.0 - 1.0)

        Returns:
            Ответ от модели
        """
        session = await self._get_session()

        # Формируем список сообщений с системным промптом
        full_messages = []
        if system_prompt:
            full_messages.append({
                "role": "system",
                "content": system_prompt
            })
        full_messages.extend(messages)

        payload = {
            "model": model,
            "messages": full_messages,
            "temperature": temperature
        }

        try:
            async with session.post(
                f"{self.BASE_URL}/v1/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OnlySq API error: {response.status} - {error_text}")
                    return "Извини, произошла ошибка при обращении к API."

                data = await response.json()
                return data['choices'][0]['message']['content']

        except asyncio.TimeoutError:
            logger.error("OnlySq API timeout")
            return "Извини, запрос занял слишком много времени."
        except Exception as e:
            logger.error(f"OnlySq API error: {e}")
            return "Произошла ошибка при обработке запроса."

    async def generate_bot_prompt(self, user_description: str) -> str:
        """
        Генерация системного промпта для бота на основе описания пользователя

        Args:
            user_description: Описание желаемого поведения бота от пользователя

        Returns:
            Сгенерированный системный промпт
        """
        meta_prompt = (
            "Ты - эксперт по созданию системных промптов для чат-ботов. "
            "Пользователь описал, каким должен быть его бот. "
            "Создай детальный системный промпт на русском языке, который определит:"
            "\n1. Личность и характер бота"
            "\n2. Стиль общения"
            "\n3. Основные функции и возможности"
            "\n4. Ограничения и правила поведения"
            "\n\nОписание от пользователя: {description}"
            "\n\nСгенерируй системный промпт (150-300 слов):"
        )

        messages = [
            {
                "role": "user",
                "content": meta_prompt.format(description=user_description)
            }
        ]

        system_prompt = await self.chat(messages, model="gpt-4o-mini", temperature=0.8)
        return system_prompt

    async def close(self):
        """Закрыть сессию"""
        if self.session and not self.session.closed:
            await self.session.close()
