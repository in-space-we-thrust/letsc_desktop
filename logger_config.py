import logging
import logging.handlers
import os
import json
from datetime import datetime

# Глобальный словарь для отслеживания логгеров
LOGGERS = {}
DEFAULT_SETTINGS = {
    "default_level": "INFO",
    "loggers": {},
    "log_to_file": True,
    "log_to_console": True,
    "log_directory": "logs"
}

def load_log_settings():
    """Загрузка настроек логирования из файла"""
    try:
        with open('log_settings.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_SETTINGS

def get_log_level(level_name):
    """Преобразование строкового названия уровня в константу logging"""
    return getattr(logging, level_name.upper(), logging.INFO)

def setup_logger(name, log_level=None):
    """Создание или получение существующего логгера с заданными настройками"""
    if name in LOGGERS:
        return LOGGERS[name]

    settings = load_log_settings()
    
    # Определение уровня логирования
    if log_level is None:
        level = get_log_level(settings['loggers'].get(name, settings['default_level']))
    else:
        level = get_log_level(log_level)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Очистка существующих обработчиков
    logger.handlers = []

    if settings['log_to_file']:
        # Создание директории для логов если её нет
        log_dir = settings['log_directory']
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Файловый обработчик с ротацией
        log_file = os.path.join(log_dir, f'{name}_{datetime.now():%Y%m%d}.log')
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1024*1024,
            backupCount=5
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    if settings['log_to_console']:
        # Консольный обработчик
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(name)s - %(levelname)s - %(message)s'
        ))
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    LOGGERS[name] = logger
    return logger

def set_log_level(name=None, level=None):
    """Изменение уровня логирования для конкретного логгера или всех логгеров"""
    if level is None:
        return

    level = get_log_level(level)
    
    if name is None:
        # Изменить уровень для всех логгеров
        for logger in LOGGERS.values():
            logger.setLevel(level)
            for handler in logger.handlers:
                handler.setLevel(level)
    elif name in LOGGERS:
        # Изменить уровень для конкретного логгера
        logger = LOGGERS[name]
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)