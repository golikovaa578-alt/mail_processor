import os
import json
import logging

logger = logging.getLogger(__name__)


class Email:
    def __init__(self, filepath, subject, sender, body, raw_text):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.subject = subject or ""
        self.sender = sender or ""
        self.body = body or ""
        self.raw_text = raw_text or ""

    def get_full_text(self):
        return f"{self.subject} {self.sender} {self.body}".lower()
    def __repr__(self):
        return f"Email(file={self.filename}, subject={self.subject!r})"


class EmailReader:
    SUPPORTED_FORMATS = [".txt", ".json", ""]
    def read_all(self, inbox_path):
        pismа = []

        if not os.path.exists(inbox_path):
            logger.error(f"Папка не существует: {inbox_path}")
            return pismа

        for filename in os.listdir(inbox_path):
            filepath = os.path.join(inbox_path, filename)
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
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        # пробуем читать как текст
        raw_text = self._read_raw(filepath)
        if raw_text is None:
            return None
        if ext == ".json" or (raw_text.strip().startswith("{")):
            return self._parse_json(filepath, raw_text)
        return self._parse_text(filepath, raw_text)

    def _read_raw(self, filepath):
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
        subject = ""
        sender = ""
        body_lines = []
        in_body = False

        for line in raw_text.splitlines():
            line_stripped = line.strip()
            if not line_stripped and not in_body and (subject or sender):
                in_body = True
                continue
            if in_body:
                body_lines.append(line)
                continue
            low = line_stripped.lower()
            if low.startswith("subject:") or low.startswith("тема:"):
                subject = self._extract_header_value(line_stripped)
            elif low.startswith("from:") or low.startswith("от кого:"):
                sender = self._extract_header_value(line_stripped)
        if not subject and not sender:
            body_lines = raw_text.splitlines()
        body = "\n".join(body_lines).strip()
        return Email(filepath, subject, sender, body, raw_text)

    def _parse_json(self, filepath, raw_text):
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
        if ":" in header_line:
            return header_line.split(":", 1)[1].strip()
        return ""
