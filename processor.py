import os
import shutil
import logging
import datetime
from classifier import ALL_CATEGORIES, UNKNOWN

logger = logging.getLogger(__name__)


class ProcessingStats:
    """Статистика по итогам обработки"""

    def __init__(self):
        self.total = 0
        self.by_category = {cat: 0 for cat in ALL_CATEGORIES}
        self.errors = 0
        self.start_time = datetime.datetime.now()
        self.end_time = None

    def add(self, category):
        self.total += 1
        self.by_category[category] = self.by_category.get(category, 0) + 1

    def add_error(self):
        self.errors += 1
        self.total += 1

    def finish(self):
        self.end_time = datetime.datetime.now()

    def duration_seconds(self):
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0

    def print_summary(self):
        """Выводит красивую статистику в консоль"""
        print("\n" + "=" * 50)
        print("  РЕЗУЛЬТАТЫ ОБРАБОТКИ ПОЧТЫ")
        print("=" * 50)
        print(f"  Всего обработано: {self.total}")
        print(f"  Ошибок:          {self.errors}")
        print(f"  Время:           {self.duration_seconds():.1f} сек")
        print("-" * 50)
        print("  По категориям:")
        for cat in ALL_CATEGORIES:
            count = self.by_category.get(cat, 0)
            if count > 0:
                bar = "█" * count
                print(f"  {cat:<12} {count:>3}  {bar}")
        print("=" * 50 + "\n")


class MailProcessor:
    """
    Основной обработчик.
    Берёт письма, классифицирует, перемещает в нужные папки, ведёт лог.
    """

    def __init__(self, reader, classifier, output_dir="processed", log_file="processing.log"):
        self.reader = reader
        self.classifier = classifier
        self.output_dir = output_dir
        self.log_file = log_file

    def process(self, inbox_path):
        """
        Главный метод - запускает всю обработку.
        Возвращает ProcessingStats.
        """
        stats = ProcessingStats()

        # создаём папки для категорий если их нет
        self._prepare_output_dirs()

        # читаем все письма
        pisma = self.reader.read_all(inbox_path)
        logger.info(f"Начинаем обработку {len(pisma)} писем")

        for email in pisma:
            try:
                result = self.classifier.classify(email)
                self._move_email(email, result.category)
                self._write_log(email, result)
                stats.add(result.category)

                logger.info(
                    f"{email.filename} -> {result.category} ({result.reason})"
                )

            except Exception as e:
                logger.error(f"Ошибка при обработке {email.filename}: {e}")
                # пытаемся сохранить файл в unknown чтобы не потерять
                try:
                    self._move_email(email, UNKNOWN)
                except Exception:
                    pass
                stats.add_error()

        stats.finish()
        return stats

    def _prepare_output_dirs(self):
        """Создаёт папки для всех категорий"""
        for category in ALL_CATEGORIES:
            category_dir = os.path.join(self.output_dir, category)
            os.makedirs(category_dir, exist_ok=True)

    def _move_email(self, email, category):
        """Перемещает файл письма в папку категории"""
        dest_dir = os.path.join(self.output_dir, category)
        dest_path = os.path.join(dest_dir, email.filename)

        # если файл с таким именем уже есть - добавляем суффикс
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(email.filename)
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            dest_path = os.path.join(dest_dir, f"{base}_{timestamp}{ext}")

        shutil.copy2(email.filepath, dest_path)
        logger.debug(f"Скопировано: {email.filename} -> {category}/")

    def _write_log(self, email, result):
        """Дописывает запись в лог-файл"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = (
            f"{timestamp} | {email.filename:<20} | "
            f"{result.category:<12} | conf={result.confidence:.2f} | {result.reason}\n"
        )
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
