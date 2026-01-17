# CART-GET.PY

import boto3
import os
import logging
from shared.responses import success_response, error_response
from shared.cart import get_cart, get_user_id, get_cart_id, build_cart_response


dynamodb = boto3.resource('dynamodb')

carts_table_name = os.getenv('CARTS_TABLE')
if not carts_table_name:
    raise RuntimeError("Missing required environment variable: CARTS_TABLE")
carts_table = dynamodb.Table(carts_table_name)

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level, logging.INFO))


# ----------------------
# Lambda Handler
# ----------------------

def lambda_handler(event, context):
    """
    Get cart
    Routes: GET /api/cart and GET /api/cart/auth
    """
    try:
        # Get userId from JWT authorizer or use cookie for guest
        user_id = get_user_id(event)
        cart_id = get_cart_id(user_id)

        # Fetch cart from DynamoDB
        cart = get_cart(cart_id, carts_table)
        
        if not cart:
            # Return empty cart
            return success_response({
                'cart': {
                    'cartId': cart_id,
                    'userId': user_id,
                    'items': [],
                    'itemCount': 0,
                    'totalWeight': 0,
                    'subtotal': 0
                }
            })
        
        # Build response cart
        response_cart = build_cart_response(cart_id, cart.get('items', {}), user_id)

        # Set cart cookie for guest users
        response = success_response({'cart': response_cart})

        if user_id.startswith('guest_'):
            cookie_cart_id = user_id.replace('guest_', '')
            response['headers']['Set-Cookie'] = f'cartId={cookie_cart_id}; Path=/; Max-Age=2592000; SameSite=Lax'
        
        return response
        
    except Exception as e:
        logger.error(f'Error: {str(e)}')
        return error_response(500, f'Internal server error: {str(e)}')
