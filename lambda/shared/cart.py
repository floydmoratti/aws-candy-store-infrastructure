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
    try:
        response = carts_table.get_item(Key={'cartId': cart_id})
        return response.get('Item')
    except Exception as e:
        logger.error(f'Error fetching cart: {str(e)}')
        return None


def get_user_id(event):
    """Extract userId from JWT authorizer claims or generate guest ID from cookie"""
    # Check for JWT authorizer claims (authenticated user)
    if 'requestContext' in event and 'authorizer' in event['requestContext']:
        claims = event['requestContext']['authorizer'].get('claims', {})
        if 'sub' in claims:
            return claims['sub']  # Cognito user ID
    
    # Guest user - check for cart cookie
    headers = event.get('headers', {})
    cookies = headers.get('cookie', '') or headers.get('Cookie', '')
    
    if cookies:
        for cookie in cookies.split(';'):
            cookie = cookie.strip()
            if cookie.startswith('cartId='):
                return f"guest_{cookie.split('=')[1]}"
    
    # New guest user
    return f"guest_{str(uuid.uuid4())}"


def get_cart_id(user_id):
    """Generate cart ID based on user type"""
    if user_id.startswith('guest_'):
        return user_id.replace('guest_', 'cart_')
    else:
        return f"cart_{user_id}"
    

def build_cart_response(cart_id, items, user_id):
    """Build cart response matching frontend expectations"""
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

    return {
        'cartId': cart_id,
        'userId': user_id,
        'items': cart_items,
        'itemCount': len(cart_items),
        'totalWeight': total_weight,
        'subtotal': round(subtotal, 2)
    }
