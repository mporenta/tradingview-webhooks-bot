import logging
import os

def get_logger(name, level=logging.DEBUG):
    fmt = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    logger = logging.getLogger(name)
    
    # Stream handler (console)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    
    # File handler
    logfile = os.getenv('TBOT_LOGFILE', 'app.log')  # Default to app.log if TBOT_LOGFILE is not set
    fh = logging.FileHandler(logfile)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    
    logger.setLevel(level)
    return logger
