#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
База данных для хранения информации о ботах
"""

import sqlite3
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с SQLite БД"""

    def __init__(self, db_path: str = 'bots.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                bot_name TEXT NOT NULL,
                bot_token TEXT NOT NULL,
                system_prompt TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_id ON bots(user_id)
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized")

    def create_bot(
        self,
        user_id: int,
        bot_name: str,
        bot_token: str,
        system_prompt: str,
        description: str = ""
    ) -> int:
        """Создать запись о новом боте"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO bots (user_id, bot_name, bot_token, system_prompt, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, bot_name, bot_token, system_prompt, description))

        bot_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Created bot {bot_id} for user {user_id}")
        return bot_id

    def get_bot(self, bot_id: int) -> Optional[Dict]:
        """Получить информацию о боте"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM bots WHERE id = ?', (bot_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_user_bots(self, user_id: int) -> List[Dict]:
        """Получить все боты пользователя"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            'SELECT * FROM bots WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_all_active_bots(self) -> List[Dict]:
        """Получить все активные боты"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM bots WHERE is_active = 1')
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def update_bot_status(self, bot_id: int, is_active: bool):
        """Обновить статус бота"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            'UPDATE bots SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (is_active, bot_id)
        )

        conn.commit()
        conn.close()
        logger.info(f"Updated bot {bot_id} status to {is_active}")

    def delete_bot(self, bot_id: int):
        """Удалить бота"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM bots WHERE id = ?', (bot_id,))

        conn.commit()
        conn.close()
        logger.info(f"Deleted bot {bot_id}")

    def get_bot_by_token(self, bot_token: str) -> Optional[Dict]:
        """Получить бота по токену"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM bots WHERE bot_token = ?', (bot_token,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None
