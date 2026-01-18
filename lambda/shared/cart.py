# CART.PY

import os
import logging
import uuid
from decimal import Decimal


log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level, logging.INFO))


# ----------------------
# Cart Functions
# ----------------------

def get_cart(cart_id, carts_table):
    """Fetch cart from DynamoDB"""

    log_debug("Fetching cart from DynamoDB", function="get_cart()", cart_id=cart_id, table="Carts")

    try:
        response = carts_table.get_item(Key={'cartId': cart_id})

        item = response.get('Item')
        if not item:
            log_debug("Cart not found", function="get_cart()", cart_id=cart_id)
            return None

        log_debug("Cart fetched from DynamoDB", function="get_cart()", cart_id=cart_id)

        return item
    
    except Exception as e:
        logger.error(f'Error fetching cart: {str(e)}')
        return None


def get_user_id(event):
    """Extract userId from JWT authorizer claims or generate guest ID from cookie"""

    log_debug("Extracting userId", function="get_user_id()")

    # Check for JWT authorizer claims
    if 'requestContext' in event and 'authorizer' in event['requestContext']:
        claims = event['requestContext']['authorizer'].get('claims', {})
        if 'sub' in claims:
            log_debug("Cognito user ID found in event", function="get_user_id()", user_id=claims['sub'])
            return claims['sub']  # Cognito user ID
    
    log_debug("No Cognito user ID found in event, checking cookies", function="get_user_id()")

    # Guest user - check for cart cookie
    headers = event.get('headers', {})
    cookies = headers.get('cookie', '') or headers.get('Cookie', '')
    
    if cookies:
        for cookie in cookies.split(';'):
            cookie = cookie.strip()
            if cookie.startswith('cartId='):
                cart_cookie = f"guest_{cookie.split('=')[1]}"
                log_debug("Cart cookie found", function="get_user_id()", cart_cookie=cart_cookie)
                return cart_cookie
    
    # New guest user
    new_user_id = f"guest_{str(uuid.uuid4())}"

    log_debug("No cart cookie found, generated new user id", function="get_user_id()", new_user_id=new_user_id)

    return new_user_id


def get_cart_id(user_id):
    """Generate cart ID based on user type"""
    if user_id.startswith('guest_'):
        return user_id.replace('guest_', 'cart_')
    else:
        return f"cart_{user_id}"
    

def build_cart_response(cart_id, items, user_id):
    """Build cart response matching frontend expectations"""

    log_debug("Building cart response", function="build_cart_response()", cart_id=cart_id, user_id=user_id, items=items)

    cart_items = []
    subtotal = 0
    total_weight = 0

    for product_id, item in items.items():
        weight_grams = item['weightGrams']
        price_per_unit = Decimal(str(item['priceAtAdd']))
        
        # Calculate total price for this item
        # priceAtAdd is cents per 100g
        total_price = float((price_per_unit * Decimal(str(weight_grams))) / Decimal('100'))

        cart_items.append({
            'productId': product_id,
            'productName': item['productName'],
            'weightGrams': weight_grams,
            'pricePerUnit': float(price_per_unit),
            'totalPrice': round(total_price, 2)
        })

        subtotal += total_price
        total_weight += weight_grams

    response = {
        'cartId': cart_id,
        'userId': user_id,
        'items': cart_items,
        'itemCount': len(cart_items),
        'totalWeight': total_weight,
        'subtotal': round(subtotal, 2)
    }

    log_debug("Response built", function="build_cart_response()", response=response)

    return response


def log_debug(msg, **data):
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("%s | %s", msg, data)
