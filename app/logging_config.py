"""Configuracao de logs da aplicacao.

O uvicorn so configura os proprios loggers; sem isto, os logs ``dashboard.*`` (acesso, cache,
seguranca) ficam abaixo do nivel padrao (WARNING) do root e nunca aparecem.
"""
import logging
import logging.config


def setup_logging(level: str = "INFO") -> None:
    name = (level or "INFO").upper()
    if not isinstance(logging.getLevelName(name), int):
        name = "INFO"
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,  # preserva os loggers do uvicorn
            "formatters": {
                "default": {"format": "%(asctime)s %(levelname)s [%(name)s] %(message)s"},
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "default", "stream": "ext://sys.stderr"},
            },
            "loggers": {
                "dashboard": {"handlers": ["console"], "level": name, "propagate": False},
            },
        }
    )
