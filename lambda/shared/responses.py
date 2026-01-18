# RESPONSES.PY

import json
import os
import logging

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level, logging.INFO))


DEFAULT_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Credentials': True
}


# ----------------------
# Response Functions
# ----------------------

def success_response(data, status_code=200):

    log_debug("Generating success response", function="success_response()", status_code=200, data=data)

    return {
        'statusCode': status_code,
        'headers': DEFAULT_HEADERS,
        'body': json.dumps(data, default=str)
    }


def error_response(status_code, message):
    
    log_debug("Generating error response", function="error_response()", status_code=status_code, message=message)

    return {
        'statusCode': status_code,
        'headers': DEFAULT_HEADERS,
        'body': json.dumps({'error': message})
    }


def log_debug(msg, **data):
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("%s | %s", msg, data)
