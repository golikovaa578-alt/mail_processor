import os
import json
import logging

logger = logging.getLogger(__name__)


class Email:
    """Просто контейнер для письма"""

    def __init__(self, filepath, subject, sender, body, raw_text):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.subject = subject or ""
        self.sender = sender or ""
        self.body = body or ""
        self.raw_text = raw_text or ""

    def get_full_text(self):
        """Возвращает весь текст письма для анализа"""
        return f"{self.subject} {self.sender} {self.body}".lower()

    def __repr__(self):
        return f"Email(file={self.filename}, subject={self.subject!r})"


class EmailReader:
    """Читает письма из папки, парсит их содержимое"""

    SUPPORTED_FORMATS = [".txt", ".json", ""]  # пустая строка - файл без расширения

    def read_all(self, inbox_path):
        """
        Читает все письма из папки.
        Возвращает список Email объектов.
        Письма, которые не удалось прочитать, пропускаются с логом.
        """
        pismа = []  # да, можно и так назвать

        if not os.path.exists(inbox_path):
            logger.error(f"Папка не существует: {inbox_path}")
            return pismа

        for filename in os.listdir(inbox_path):
            filepath = os.path.join(inbox_path, filename)

            # пропускаем директории и системные файлы типа .DS_Store
            if os.path.isdir(filepath):
                continue
            if filename.startswith("."):
                logger.debug(f"Пропускаем системный файл: {filename}")
                continue

            try:
                email = self._read_one(filepath)
                if email is not None:
                    pismа.append(email)
                    logger.debug(f"Прочитано: {filename}")
            except Exception as e:
                logger.warning(f"Не удалось прочитать {filename}: {e}")

        logger.info(f"Прочитано писем: {len(pismа)} из {inbox_path}")
        return pismа

    def _read_one(self, filepath):
        """
        Читает одно письмо.
        Определяет формат по расширению и содержимому.
        """
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()

        # пробуем читать как текст
        raw_text = self._read_raw(filepath)
        if raw_text is None:
            return None

        # если расширение .json или содержимое похоже на json - парсим как json
        if ext == ".json" or (raw_text.strip().startswith("{")):
            return self._parse_json(filepath, raw_text)

        # всё остальное - как обычный текст (письмо в формате заголовки + тело)
        return self._parse_text(filepath, raw_text)

    def _read_raw(self, filepath):
        """Читает файл как текст, пробует разные кодировки"""
        for encoding in ["utf-8", "cp1251", "latin-1"]:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Ошибка чтения {filepath}: {e}")
                return None

        logger.warning(f"Не удалось декодировать файл: {filepath}")
        return None

    def _parse_text(self, filepath, raw_text):
        """
        Парсит письмо в текстовом формате.
        Заголовки могут быть на русском или английском.
        """
        subject = ""
        sender = ""
        body_lines = []
        in_body = False

        for line in raw_text.splitlines():
            line_stripped = line.strip()

            # пустая строка после заголовков = начало тела
            if not line_stripped and not in_body and (subject or sender):
                in_body = True
                continue

            if in_body:
                body_lines.append(line)
                continue

            # ищем заголовки (и английские и русские варианты)
            low = line_stripped.lower()
            if low.startswith("subject:") or low.startswith("тема:"):
                subject = self._extract_header_value(line_stripped)
            elif low.startswith("from:") or low.startswith("от кого:"):
                sender = self._extract_header_value(line_stripped)

        # если заголовков не нашли - весь текст это тело
        if not subject and not sender:
            body_lines = raw_text.splitlines()

        body = "\n".join(body_lines).strip()
        return Email(filepath, subject, sender, body, raw_text)

    def _parse_json(self, filepath, raw_text):
        """Парсит письмо в JSON формате"""
        try:
            data = json.loads(raw_text)
            subject = data.get("subject", "")
            sender = data.get("from", "")
            body = data.get("body", "")
            return Email(filepath, subject, sender, body, raw_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Невалидный JSON в {filepath}: {e}")
            # фолбек - читаем как обычный текст
            return self._parse_text(filepath, raw_text)

    def _extract_header_value(self, header_line):
        """Вытаскивает значение из строки вида 'Key: Value'"""
        if ":" in header_line:
            return header_line.split(":", 1)[1].strip()
        return ""
