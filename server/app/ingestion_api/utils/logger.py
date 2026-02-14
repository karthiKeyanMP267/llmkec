import logging


_def_level = logging.INFO
logging.basicConfig(level=_def_level, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(_def_level)
    return logger
