import argparse
import logging
import sys
import os

from email_reader import EmailReader
from classifier import EmailClassifier
from processor import MailProcessor


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Система обработки корпоративной почты"
    )
    parser.add_argument(
        "--inbox",
        default="inbox",
        help="Папка с входящими письмами (по умолчанию: inbox)"
    )
    parser.add_argument(
        "--output",
        default="processed",
        help="Папка для результатов (по умолчанию: processed)"
    )
    parser.add_argument(
        "--log-file",
        default="processing.log",
        help="Файл лога (по умолчанию: processing.log)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Подробный вывод"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    logger.info(f"Запуск обработки почты")
    logger.info(f"Входящие: {args.inbox}")
    logger.info(f"Результаты: {args.output}")

    if not os.path.exists(args.inbox):
        logger.error(f"Папка не найдена: {args.inbox}")
        sys.exit(1)

    reader = EmailReader()
    classifier = EmailClassifier()
    processor = MailProcessor(
        reader=reader,
        classifier=classifier,
        output_dir=args.output,
        log_file=args.log_file,
    )

    stats = processor.process(args.inbox)
    stats.print_summary()
    sys.exit(0 if stats.errors == 0 else 1)


if __name__ == "__main__":
    main()
