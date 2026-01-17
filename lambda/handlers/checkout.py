# CHECKOUT.PY

import json
import boto3
import os
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from shared.responses import success_response, error_response
from shared.cart import get_cart, get_user_id, build_cart_response
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

orders_table_name = os.getenv('ORDERS_TABLE')
if not orders_table_name:
    raise RuntimeError("Missing required environment variable: ORDERS_TABLE")
orders_table = dynamodb.Table(orders_table_name)

TAX_RATE = Decimal(os.getenv('TAX_RATE', '0.08'))
SHIPPING_COST = Decimal(os.getenv('SHIPPING_COST', '2.99'))
PRICE_TOLERANCE = Decimal('0.01')

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level, logging.INFO))


# ----------------------
# Lambda Handler
# ----------------------

def lambda_handler(event, context):
    """
    Process checkout and create order
    Route: POST /api/checkout/auth
    """
    try:
        # Get userId from JWT authorizer
        user_id = get_user_id(event)
        if not user_id:
            return error_response(401, 'Unauthorized')
        
        cart_id = f"cart_{user_id}"

        # Parse request body
        body = json.loads(event['body'])

        # Validate required fields
        if not validate_checkout_data(body):
            return error_response(400, 'Invalid checkout data')
        
        # Get cart
        cart = get_cart(cart_id, carts_table)
        if not cart or not cart.get('items'):
            return error_response(400, 'Cart is empty')
        
        # Verify stock availability for all items
        items = cart.get('items', {})
        for product_id, item in items.items():
            product = get_product(product_id)
            if not product:
                return error_response(400, f'Product {product_id} not found')
            
            if not product.get('isActive', False):
                return error_response(400, f'Product {product["productName"]} is no longer available')
            
            available_grams = product.get('availableGrams', 0)
            if available_grams < item['weightGrams']:
                return error_response(400, f'Insufficient stock for {product["productName"]}')
            
        # Calculate order totals
        server_subtotal = Decimal('0')
        order_items = {}

        for product_id, item in items.items():
            weight_grams = item['weightGrams']
            price_per_unit = Decimal(str(item['priceAtAdd']))
            total_price = (price_per_unit * Decimal(str(weight_grams))) / Decimal('100')

            total_price = total_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            order_items[product_id] = {
                'productId': product_id,
                'productName': item['productName'],
                'weightGrams': weight_grams,
                'priceAtAdd': float(price_per_unit),
                'totalPrice': float(total_price)
            }
            
            server_subtotal += total_price
        
        server_shipping = SHIPPING_COST
        server_tax = (server_subtotal * TAX_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        server_subtotal = server_subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        server_total = (server_shipping + server_tax + server_subtotal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Get pricing from request
        client_pricing = body.get('pricing', {})
        client_shipping = Decimal(str(client_pricing.get('shipping', 2.99)))
        client_tax = Decimal(str(client_pricing.get('tax', 0)))
        client_subtotal = Decimal(str(client_pricing.get('subtotal', 0)))
        client_total = Decimal(str(client_pricing.get('total', 0)))

        # Check client side pricing with server side
        pricing_mismatch = (
            not prices_match(server_subtotal, client_subtotal) or
            not prices_match(server_tax, client_tax) or
            not prices_match(server_shipping, client_shipping) or
            not prices_match(server_total, client_total)
        )

        # Update client side pricing if mismatching
        if pricing_mismatch:
            return {
                'statusCode': 409,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
                },
                'body': json.dumps({
                    'error': 'PRICING_MISMATCH',
                    'message': 'Pricing has changed. Please review updated totals.',
                    'pricing': {
                        'subtotal': float(server_subtotal),
                        'tax': float(server_tax),
                        'shipping': float(server_shipping),
                        'total': float(server_total)
                    }
                })
            }
        
        # Process payment (placeholder)
        payment_result = process_payment(body.get('payment', {}), server_total)

        if not payment_result['success']:
            return error_response(400, payment_result['message'])
        
        # Create order
        order_id = f"order_{str(uuid.uuid4())}"
        now = datetime.now(timezone.utc).isoformat()

        # Intitiate DynamoDB transcation
        order_item = {
            'Put': {
                'TableName': orders_table_name,
                'Item': {
                    'orderId': {'S': order_id},
                    'userId': {'S': user_id},
                    'items': {'M': to_dynamodb_items(order_items)},
                    'subtotal': {'N': str(server_subtotal)},
                    'shipping': {'N': str(server_shipping)},
                    'tax': {'N': str(server_tax)},
                    'totalAmount': {'N': str(server_total)},
                    'status': {'S': 'PAID'},
                    'paymentProvider': {'S': payment_result['provider']},
                    'paymentRef': {'S': payment_result['reference']},
                    'createdAt': {'S': now},
                    'updatedAt': {'S': now}
                },
                'ConditionExpression': 'attribute_not_exists(orderId)'
            }
        }

        stock_updates = []

        for product_id, item in items.items():
            stock_updates.append({
                'Update': {
                    'TableName': products_table_name,
                    'Key': {
                        'productId': {'S': product_id}
                    },
                    'UpdateExpression': (
                        'SET availableGrams = availableGrams - :qty, '
                        'updatedAt = :updated'
                    ),
                    'ConditionExpression': 'availableGrams >= :qty',
                    'ExpressionAttributeValues': {
                        ':qty': {'N': str(item['weightGrams'])},
                        ':updated': {'S': now}
                    }
                }
            })

        cart_update = {
            'Update': {
                'TableName': carts_table_name,
                'Key': {
                    'cartId': {'S': cart_id}
                },
                'UpdateExpression': 'SET #status = :status, updatedAt = :updated',
                'ExpressionAttributeNames': {
                    '#status': 'status'
                },
                'ExpressionAttributeValues': {
                    ':status': {'S': 'CHECKED_OUT'},
                    ':updated': {'S': now}
                }
            }
        }

        try:
            dynamodb.transact_write_items(
                TransactItems=[
                    order_item,
                    cart_update,
                    *stock_updates
                ]
            )
        except dynamodb.exceptions.TransactionCanceledException as e:
            logger.error(f'Transaction failed: {e}')
            
            # Refund payment if failed
            # refund_payment(payment_result)

            return error_response(
                409,
                'Checkout failed due to inventory change. Payment was not captured.'
            )
        
        return success_response({
            'orderId': order_id,
            'status': 'PAID',
            'totalAmount': float(server_total),
            'message': 'Order placed successfully'
        })

    except Exception as e:
        logger.error(f'Error: {str(e)}')
        return error_response(500, f'Internal server error: {str(e)}')


# ----------------------
# Helper Functions
# ----------------------

def validate_checkout_data(data):
    """Validate checkout request data"""
    required_fields = ['items', 'shipping', 'payment', 'pricing']
    
    for field in required_fields:
        if field not in data:
            return False
    
    # Validate shipping address
    shipping_fields = ['firstName', 'lastName', 'email', 'phone', 'address', 'city', 'state', 'zip']
    for field in shipping_fields:
        if field not in data['shipping'] or not data['shipping'][field]:
            return False
    
    # Validate payment info
    payment_fields = ['cardName', 'cardLast4', 'cardExpiry']
    for field in payment_fields:
        if field not in data['payment'] or not data['payment'][field]:
            return False
    
    return True


def process_payment(payment_info, amount):
    """Process payment (placeholder implementation)"""

    # Placeholder validation
    if not payment_info.get('cardName'):
        return {
            'success': False,
            'message': 'Invalid card name'
        }
    
    if not payment_info.get('cardLast4'):
        return {
            'success': False,
            'message': 'Invalid card number'
        }
    
    # Simulate successful payment
    return {
        'success': True,
        'amount': amount,
        'provider': 'DEMO_PAYMENT',
        'reference': f'demo_{str(uuid.uuid4())[:8]}',
        'message': 'Payment processed successfully'
    }


def to_dynamodb_items(items: dict) -> dict:
    return {
        product_id: {
            'M': {
                'productId': {'S': item['productId']},
                'productName': {'S': item['productName']},
                'weightGrams': {'N': str(item['weightGrams'])},
                'priceAtAdd': {'N': str(item['priceAtAdd'])},
                'totalPrice': {'N': str(item['totalPrice'])}
            }
        }
        for product_id, item in items.items()
    }


def prices_match(a: Decimal, b: Decimal) -> bool:
            return abs(a - b) <= PRICE_TOLERANCE
