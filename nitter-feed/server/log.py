import logging


def set_global_log_level(level: str):

    if level is None:
        return
    numeric_loglevel = getattr(logging, level.upper(), None)
    if not isinstance(numeric_loglevel, int):
        raise ValueError('Invalid log level: %s' % level)
    

    logging.basicConfig(level=numeric_loglevel,
                        encoding='utf-8',
                        #format="%(asctime)s,%(msecs).3d   %(levelname)s:%(module)s  %(message)s",
                        #datefmt="%H:%M:%S",
                        )
