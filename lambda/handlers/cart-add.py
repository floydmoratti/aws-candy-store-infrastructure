# CART-ADD.PY

import json
import boto3
import os
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from shared.responses import success_response, error_response
from shared.cart import get_user_id, get_cart_id, build_cart_response
from shared.products import get_product


dynamodb = boto3.resource('dynamodb')

products_table_name = os.getenv('PRODUCTS_TABLE')
if not products_table_name:
    raise RuntimeError("Missing required environment variable: PRODUCTS_TABLE")
products_table = dynamodb.Table(products_table_name)

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
    Add item to cart
    Routes: POST /api/cart/items/{productId} and POST /api/cart/items/{productId}/auth
    """
    
    log_debug("Received event", function="lambda_handler()", event=json.dumps(event, indent=2, default=str))

    try:
        # Extract productId from path
        product_id = event['pathParameters']['productId']

        # Parse request body
        body = json.loads(event['body'])
        weight_grams = body.get('weightGrams')

        if not weight_grams or weight_grams <= 0:
            return error_response(400, 'Invalid weightGrams')
        
        # Get userId from JWT authorizer or use cookie for guest
        user_id = get_user_id(event)
        cart_id = get_cart_id(user_id)
        log_debug("Resolved cart id", function="lambda_handler()", user_id=user_id, cart_id=cart_id)

        # Fetch product details
        product = get_product(product_id, products_table)
        if not product:
            return error_response(404, 'Product not found')        
        if not product.get('isActive', False):
            return error_response(400, 'Product is not available')
        
        # Check stock availability
        available_grams = product.get('availableGrams', 0)
        if available_grams < weight_grams:
            return error_response(400, 'Insufficient stock')
        log_debug("Resolved product", function="lambda_handler()", product=product, available_grams=available_grams)
        
        # Get or create cart
        cart = get_or_create_cart(cart_id, user_id)

        # Calculate price per 100g
        price_per_unit = Decimal(str(product['price']))  # price is in cents per 100g

        # Add or update item in cart
        items = cart.get('items', {})

        if product_id in items:
            # Update existing item
            items[product_id]['weightGrams'] = weight_grams
        else:
            # Add new item
            items[product_id] = {
                'productId': product_id,
                'productName': product['productName'],
                'weightGrams': weight_grams,
                'priceAtAdd': float(price_per_unit)
            }
        log_debug("Resolved cart", function="lambda_handler()", cart=cart, price_per_unit=price_per_unit, items=items)
        
        # Update cart in DynamoDB
        now = datetime.now(timezone.utc).isoformat()
        expires_at = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())

        log_debug("Updating cart in DynamoDB", function="lambda_handler()", cart_id=cart_id, table="Carts")

        carts_table.update_item(
            Key={'cartId': cart_id},
            UpdateExpression='SET items = :items, updatedAt = :updated, expiresAt = :expires, userId = :userId, #status = :status',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':items': items,
                ':updated': now,
                ':expires': expires_at,
                ':userId': user_id,
                ':status': 'ACTIVE'
            }
        )

        log_debug("Updated cart in DynamoDB", function="lambda_handler()", cart_id=cart_id, table="Carts")

        # Build response cart
        response_cart = build_cart_response(cart_id, items, user_id)

        return success_response({
            'cart': response_cart,
            'message': 'Item added to cart'
        })

    except Exception as e:
        logger.error(f'Error: {str(e)}')
        return error_response(500, f'Internal server error: {str(e)}')


# ----------------------
# Helper Functions
# ----------------------

def get_or_create_cart(cart_id, user_id):
    """Get existing cart or create new one"""

    log_debug("Fetching cart from DynamoDB", function="get_or_create_cart()", cart_id=cart_id, table="Carts")

    try:
        response = carts_table.get_item(Key={'cartId': cart_id})
        if 'Item' in response:
            log_debug("Cart fetched from DynamoDB", function="get_or_create_cart()", cart=response['Item'])
            return response['Item']
        else:
            # Return empty cart structure
            log_debug("No cart in DynamoDB", function="get_or_create_cart()")
            return {
                'cartId': cart_id,
                'userId': user_id,
                'items': {},
                'status': 'ACTIVE'
            }
    except Exception as e:
        logger.error(f'Error fetching cart: {str(e)}')
        return {
            'cartId': cart_id,
            'userId': user_id,
            'items': {},
            'status': 'ACTIVE'
        }
    

def log_debug(msg, **data):
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("%s | %s", msg, data)
