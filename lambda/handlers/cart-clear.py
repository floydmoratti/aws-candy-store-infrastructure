# CART-CLEAR.PY

import boto3
import os
import logging
from datetime import datetime, timedelta, timezone
from shared.responses import success_response, error_response
from shared.cart import get_user_id, get_cart_id


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
    Clear entire cart
    Routes: DELETE /api/cart and DELETE /api/cart/auth
    """
    try:
        # Get userId from JWT authorizer or use cookie for guest
        user_id = get_user_id(event)
        cart_id = get_cart_id(event, user_id)

        # Clear cart by setting items to empty dict
        now = datetime.now(timezone.utc).isoformat()
        expires_at = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())

        carts_table.update_item(
            Key={'cartId': cart_id},
            UpdateExpression='SET items = :items, updatedAt = :updated, expiresAt = :expires, #status = :status',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':items': {},
                ':updated': now,
                ':expires': expires_at,
                ':status': 'ACTIVE'
            }
        )

        # Build empty cart response
        response_cart = {
            'cartId': cart_id,
            'userId': user_id,
            'items': [],
            'itemCount': 0,
            'totalWeight': 0,
            'subtotal': 0
        }

        return success_response({
            'cart': response_cart,
            'message': 'Cart cleared'
        })
        
    except Exception as e:
        logger.error(f'Error: {str(e)}')
        return error_response(500, f'Internal server error: {str(e)}')
