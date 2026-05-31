import re
import logging

logger = logging.getLogger(__name__)

# Категории
CRITICAL = "critical"
REQUESTS = "requests"
MONITORING = "monitoring"
SPAM = "spam"
INFO = "info"
UNKNOWN = "unknown"

ALL_CATEGORIES = [CRITICAL, REQUESTS, MONITORING, SPAM, INFO, UNKNOWN]


class ClassificationResult:
    """Результат классификации одного письма"""

    def __init__(self, category, reason, confidence):
        self.category = category
        self.reason = reason      # почему так решили
        self.confidence = confidence  # от 0 до 1, просто для информации

    def __repr__(self):
        return f"ClassificationResult(category={self.category!r}, reason={self.reason!r})"


class EmailClassifier:
    """
    Классифицирует письма по правилам.
    Правила проверяются по приоритету - первое совпадение выигрывает.
    """

    # Слова-триггеры для каждой категории
    # Порядок важен - более специфичные правила выше

    CRITICAL_keywords = [
        "критический инцидент",
        "критическая ошибка",
        "сервис недоступен",
        "сервис упал",
        "полностью остановлена",
        "работа остановлена",
        "ошибка 500",
        "error 500",
        "недоступен",
        "не отвечает",
        "упал",
        "горит",
        "срочно",
        "urgent",
        "critical",
        "down",
        "outage",
    ]

    MONITORING_keywords = [
        "автоматическое уведомление",
        "это письмо сгенерировано автоматически",
        "сгенерировано автоматически",
        "система мониторинга",
        "alertmanager",
        "grafana",
        "nagios",
        "zabbix",
        "prometheus",
        "healthcheck",
        "health check",
        "метрика",
        "cpu usage",
        "memory usage",
        "disk usage",
        "[info]",
        "[warn]",
        "[alert]",
        "no-reply@monitoring",
        "alerts@",
        "noreply@monitoring",
    ]

    SPAM_keywords = [
        "ваш аккаунт будет заблокирован",
        "аккаунт заблокирован",
        "подтвердите данные",
        "введите пароль",
        "срочно подтвердите",
        "вы выиграли",
        "получите приз",
        "бесплатно",
        "скидка 90",
        "нигерийский принц",
        "перейдите по ссылке",
        "click here",
        "verify your account",
        "your account has been",
        "congratulations you won",
        "free offer",
        "limited time",
    ]

    REQUESTS_keywords = [
        "запрос доступа",
        "прошу выдать доступ",
        "предоставить доступ",
        "нужны права",
        "нужен доступ",
        "запрос на",
        "заявка на",
        "оформление нового сотрудника",
        "новый сотрудник",
        "vpn",
        "учётная запись",
        "учетная запись",
        "сброс пароля",
        "reset password",
        "access request",
        "прошу установить",
        "нужно установить",
        "не работает принтер",
        "не работает компьютер",
        "ноутбук не включается",
        "id заявки",
        "обращаемся повторно",
        # добавили по результатам анализа реальных писем
        "неисправность оборудования",
        "сломался",
        "нужна замена",
        "зависает",
        "не включается",
        "ошибка в excel",
        "ошибка в word",
        "браузер",
        "запрос от внешнего",
        "вопрос по заявке",
        "прошу рассмотреть",
    ]

    INFO_keywords = [
        "дайджест",
        "newsletter",
        "рассылка",
        "новости компании",
        "корпоративный портал",
        "итоги квартала",
        "новые сотрудники",
        "изменения в политике",
        "приглашаем",
        "напоминаем",
        "сообщаем",
        "информируем",
        "обновление системы",
        "плановые работы",
        "техническое обслуживание",
        "no-reply@",
        "noreply@",
    ]

    def classify(self, email):
        """
        Классифицирует письмо.
        Возвращает ClassificationResult.
        """
        text = email.get_full_text()
        sender = email.sender.lower()

        # порядок важен! сначала spam (безопасность прежде всего),
        # потом critical, потом monitoring, потом requests, потом info

        # 1. Спам - проверяем отдельно, он может замаскироваться
        result = self._check_spam(text, sender)
        if result:
            return result

        # 2. Критические инциденты
        result = self._check_critical(text, sender)
        if result:
            return result

        # 3. Мониторинг - автоматические уведомления
        result = self._check_monitoring(text, sender)
        if result:
            return result

        # 4. Заявки и запросы
        result = self._check_requests(text, sender)
        if result:
            return result

        # 5. Информационные рассылки
        result = self._check_info(text, sender)
        if result:
            return result

        # 6. Ничего не подошло
        logger.debug(f"Письмо не классифицировано: {email.filename}")
        return ClassificationResult(
            category=UNKNOWN,
            reason="не совпало ни с одним правилом",
            confidence=0.0
        )

    def _check_spam(self, text, sender):
        for keyword in self.SPAM_keywords:
            if keyword in text:
                return ClassificationResult(
                    category=SPAM,
                    reason=f"найдено ключевое слово спама: '{keyword}'",
                    confidence=0.9
                )
        return None

    def _check_critical(self, text, sender):
        # критические письма часто имеют несколько признаков сразу
        matches_count = 0
        first_match = None

        for keyword in self.CRITICAL_keywords:
            if keyword in text:
                matches_count += 1
                if first_match is None:
                    first_match = keyword

        if matches_count >= 1:
            confidence = min(0.5 + matches_count * 0.1, 1.0)
            return ClassificationResult(
                category=CRITICAL,
                reason=f"найдено {matches_count} признаков инцидента, первый: '{first_match}'",
                confidence=confidence
            )
        return None

    def _check_monitoring(self, text, sender):
        # проверяем отправителя отдельно - мониторинг часто шлёт с определённых адресов
        monitoring_senders = ["no-reply@monitoring", "alerts@", "noreply@monitoring", "alertmanager@"]
        for ms in monitoring_senders:
            if ms in sender:
                return ClassificationResult(
                    category=MONITORING,
                    reason=f"отправитель мониторинга: содержит '{ms}'",
                    confidence=0.95
                )

        for keyword in self.MONITORING_keywords:
            if keyword in text:
                return ClassificationResult(
                    category=MONITORING,
                    reason=f"найдено ключевое слово мониторинга: '{keyword}'",
                    confidence=0.8
                )
        return None

    def _check_requests(self, text, sender):
        for keyword in self.REQUESTS_keywords:
            if keyword in text:
                return ClassificationResult(
                    category=REQUESTS,
                    reason=f"найдено ключевое слово заявки: '{keyword}'",
                    confidence=0.8
                )
        return None

    def _check_info(self, text, sender):
        # noreply отправители без признаков мониторинга - скорее всего инфо-рассылка
        noreply_senders = ["no-reply@", "noreply@", "newsletter@", "news@"]
        for ns in noreply_senders:
            if ns in sender:
                return ClassificationResult(
                    category=INFO,
                    reason=f"отправитель рассылки: содержит '{ns}'",
                    confidence=0.75
                )

        for keyword in self.INFO_keywords:
            if keyword in text:
                return ClassificationResult(
                    category=INFO,
                    reason=f"найдено ключевое слово инфо: '{keyword}'",
                    confidence=0.7
                )
        return None
