import logging

from .config import ServiceConfig, setup_logging
from .server import run_server


def main() -> None:
    config = ServiceConfig.load()
    config.normalize()
    setup_logging(config.log_level)
    logger = logging.getLogger("moonlight_voice")
    logger.setLevel(logging.getLogger().level)
    for note in config.notes:
        logger.info(note)
    logger.info(
        "Moonlight Voice %s | host=%s | port=%s | format=%s | cache_headers=%s",
        config.version,
        config.host,
        config.port,
        config.output_format,
        config.cache_headers,
    )
    run_server(config)


if __name__ == "__main__":
    main()
