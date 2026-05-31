"""
Тесты для системы обработки почты.
Запуск: python -m pytest tests/ -v
"""
import os
import shutil
import tempfile
import pytest

from email_reader import EmailReader, Email
from classifier import EmailClassifier, CRITICAL, REQUESTS, MONITORING, SPAM, INFO, UNKNOWN
from processor import MailProcessor, ProcessingStats


# ==================== Фикстуры ====================

@pytest.fixture
def classifier():
    return EmailClassifier()


@pytest.fixture
def reader():
    return EmailReader()


@pytest.fixture
def temp_inbox():
    """Создаёт временную папку с тестовыми письмами"""
    tmpdir = tempfile.mkdtemp()
    inbox = os.path.join(tmpdir, "inbox")
    os.makedirs(inbox)
    yield inbox
    shutil.rmtree(tmpdir)


@pytest.fixture
def temp_output():
    """Временная папка для результатов"""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)


def make_email(subject="", sender="", body=""):
    """Хелпер для быстрого создания тестового письма"""
    return Email(
        filepath="/fake/path/mail_test.txt",
        subject=subject,
        sender=sender,
        body=body,
        raw_text=f"{subject} {sender} {body}"
    )


def write_email_file(inbox_dir, filename, content):
    """Записывает тестовый файл письма"""
    path = os.path.join(inbox_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ==================== Тесты EmailReader ====================

class TestEmailReader:

    def test_read_txt_letter(self, reader, temp_inbox):
        """Обычное txt письмо читается нормально"""
        content = "Subject: Тест\nFrom: user@corp.ru\n\nТело письма"
        write_email_file(temp_inbox, "mail_001.txt", content)

        emails = reader.read_all(temp_inbox)
        assert len(emails) == 1
        assert emails[0].subject == "Тест"
        assert emails[0].sender == "user@corp.ru"

    def test_read_json_letter(self, reader, temp_inbox):
        """JSON письмо парсится правильно"""
        content = '{"from": "bot@corp", "subject": "Алерт", "body": "Что-то упало"}'
        write_email_file(temp_inbox, "mail_002.json", content)

        emails = reader.read_all(temp_inbox)
        assert len(emails) == 1
        assert emails[0].subject == "Алерт"
        assert emails[0].sender == "bot@corp"

    def test_skip_ds_store(self, reader, temp_inbox):
        """Системные файлы .DS_Store игнорируются"""
        write_email_file(temp_inbox, ".DS_Store", "binary garbage")
        write_email_file(temp_inbox, "mail_003.txt", "Subject: ok\n\nтело")

        emails = reader.read_all(temp_inbox)
        assert len(emails) == 1

    def test_empty_inbox(self, reader, temp_inbox):
        """Пустая папка - пустой список"""
        emails = reader.read_all(temp_inbox)
        assert emails == []

    def test_nonexistent_inbox(self, reader):
        """Несуществующая папка - пустой список без краша"""
        emails = reader.read_all("/nonexistent/path/to/inbox")
        assert emails == []

    def test_letter_without_extension(self, reader, temp_inbox):
        """Файл без расширения тоже читается"""
        write_email_file(temp_inbox, "mail_0106", "Subject: Без расширения\n\nТело")
        emails = reader.read_all(temp_inbox)
        assert len(emails) == 1

    def test_empty_file(self, reader, temp_inbox):
        """Пустой файл не падает"""
        write_email_file(temp_inbox, "mail_empty.txt", "")
        emails = reader.read_all(temp_inbox)
        # пустой файл всё равно читается, просто пустое письмо
        assert len(emails) == 1

    def test_invalid_json_fallback(self, reader, temp_inbox):
        """Невалидный JSON читается как текст без краша"""
        write_email_file(temp_inbox, "mail_bad.json", "{not valid json at all")
        emails = reader.read_all(temp_inbox)
        assert len(emails) == 1  # не упало


# ==================== Тесты EmailClassifier ====================

class TestEmailClassifier:

    def test_classify_critical_incident(self, classifier):
        """Критический инцидент - сервис упал"""
        email = make_email(
            subject="Критический инцидент — BI-система недоступна",
            body="Работа полностью остановлена, нужна срочная помощь"
        )
        result = classifier.classify(email)
        assert result.category == CRITICAL

    def test_classify_critical_500_error(self, classifier):
        """Ошибка 500 = критическое"""
        email = make_email(subject="Ошибка 500 при работе с облачным хранилищем")
        result = classifier.classify(email)
        assert result.category == CRITICAL

    def test_classify_monitoring_alert(self, classifier):
        """Письмо от системы мониторинга"""
        email = make_email(
            sender="alerts@grafana.internal",
            subject="[INFO] CPU usage 77%",
            body="Автоматическое уведомление от системы мониторинга"
        )
        result = classifier.classify(email)
        assert result.category == MONITORING

    def test_classify_monitoring_by_sender(self, classifier):
        """Мониторинг определяется по адресу отправителя"""
        email = make_email(
            sender="no-reply@monitoring.internal",
            body="Метрика превысила порог"
        )
        result = classifier.classify(email)
        assert result.category == MONITORING

    def test_classify_spam_account_blocked(self, classifier):
        """Фишинговое письмо про блокировку аккаунта"""
        email = make_email(
            subject="Ваш аккаунт будет заблокирован",
            body="Подтвердите данные для восстановления"
        )
        result = classifier.classify(email)
        assert result.category == SPAM

    def test_classify_request_vpn(self, classifier):
        """Запрос VPN доступа"""
        email = make_email(
            subject="Запрос доступа к VPN",
            body="Нужны права на VPN для временного сотрудника"
        )
        result = classifier.classify(email)
        assert result.category == REQUESTS

    def test_classify_request_new_employee(self, classifier):
        """Оформление нового сотрудника"""
        email = make_email(
            body="Оформление нового сотрудника — прошу выдать доступ"
        )
        result = classifier.classify(email)
        assert result.category == REQUESTS

    def test_classify_info_digest(self, classifier):
        """Корпоративная рассылка"""
        email = make_email(
            subject="Дайджест новостей компании",
            body="В этом выпуске: итоги квартала, новые сотрудники"
        )
        result = classifier.classify(email)
        assert result.category == INFO

    def test_classify_unknown(self, classifier):
        """Письмо без признаков = unknown"""
        email = make_email(
            subject="Привет",
            body="Как дела?"
        )
        result = classifier.classify(email)
        assert result.category == UNKNOWN

    def test_spam_beats_critical(self, classifier):
        """Спам с критическими словами всё равно спам"""
        email = make_email(
            subject="СРОЧНО! Ваш аккаунт будет заблокирован! Критическая ошибка!",
            body="Перейдите по ссылке срочно"
        )
        result = classifier.classify(email)
        assert result.category == SPAM

    def test_empty_email(self, classifier):
        """Пустое письмо не падает"""
        email = make_email()
        result = classifier.classify(email)
        assert result.category == UNKNOWN

    @pytest.mark.parametrize("subject,expected_category", [
        ("Критический инцидент — сервер недоступен", CRITICAL),
        ("Запрос на выдачу прав", REQUESTS),
        ("Дайджест корпоративных новостей", INFO),
        ("Ваш аккаунт будет заблокирован", SPAM),
        ("Привет Иван как дела", UNKNOWN),
    ])
    def test_classify_parametrized(self, classifier, subject, expected_category):
        """Параметризованные тесты по теме письма"""
        email = make_email(subject=subject)
        result = classifier.classify(email)
        assert result.category == expected_category


# ==================== Тесты MailProcessor ====================

class TestMailProcessor:

    def test_process_creates_output_dirs(self, reader, classifier, temp_inbox, temp_output):
        """После обработки создаются папки категорий"""
        processor = MailProcessor(reader, classifier, output_dir=temp_output, log_file="/dev/null")
        processor.process(temp_inbox)

        assert os.path.isdir(os.path.join(temp_output, CRITICAL))
        assert os.path.isdir(os.path.join(temp_output, SPAM))
        assert os.path.isdir(os.path.join(temp_output, UNKNOWN))

    def test_process_moves_files(self, reader, classifier, temp_inbox, temp_output):
        """Письма копируются в правильные папки"""
        write_email_file(
            temp_inbox, "mail_crit.txt",
            "Subject: Критический инцидент\n\nСервис недоступен, работа остановлена"
        )
        write_email_file(
            temp_inbox, "mail_spam.txt",
            "Subject: Ваш аккаунт будет заблокирован\n\nПодтвердите данные"
        )

        processor = MailProcessor(reader, classifier, output_dir=temp_output, log_file="/dev/null")
        stats = processor.process(temp_inbox)

        assert stats.total == 2
        assert os.path.exists(os.path.join(temp_output, CRITICAL, "mail_crit.txt"))
        assert os.path.exists(os.path.join(temp_output, SPAM, "mail_spam.txt"))

    def test_stats_count(self, reader, classifier, temp_inbox, temp_output):
        """Статистика считается правильно"""
        write_email_file(temp_inbox, "m1.txt", "Subject: Запрос доступа к VPN\n\nНужен VPN")
        write_email_file(temp_inbox, "m2.txt", "Subject: Дайджест\n\nИтоги квартала")
        write_email_file(temp_inbox, "m3.txt", "Subject: Привет\n\nКак дела")

        processor = MailProcessor(reader, classifier, output_dir=temp_output, log_file="/dev/null")
        stats = processor.process(temp_inbox)

        assert stats.total == 3
        assert stats.errors == 0


# ==================== Тесты ProcessingStats ====================

class TestProcessingStats:

    def test_stats_add(self):
        stats = ProcessingStats()
        stats.add(CRITICAL)
        stats.add(CRITICAL)
        stats.add(SPAM)

        assert stats.total == 3
        assert stats.by_category[CRITICAL] == 2
        assert stats.by_category[SPAM] == 1

    def test_stats_errors(self):
        stats = ProcessingStats()
        stats.add_error()
        stats.add_error()

        assert stats.total == 2
        assert stats.errors == 2
