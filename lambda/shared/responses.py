# RESPONSES.PY

import json

DEFAULT_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Credentials': True
}

def success_response(data, status_code=200):
    return {
        'statusCode': status_code,
        'headers': DEFAULT_HEADERS,
        'body': json.dumps(data, default=str)
    }

def error_response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': DEFAULT_HEADERS,
        'body': json.dumps({'error': message})
    }