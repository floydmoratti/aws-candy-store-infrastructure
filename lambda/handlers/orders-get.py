# ORDERS-GET.PY

import boto3
import os
import logging
from boto3.dynamodb.conditions import Key
from shared.responses import success_response, error_response
from shared.cart import get_user_id


dynamodb = boto3.resource('dynamodb')

orders_table_name = os.getenv('ORDERS_TABLE')
if not orders_table_name:
    raise RuntimeError("Missing required environment variable: ORDERS_TABLE")
orders_table = dynamodb.Table(orders_table_name)

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level, logging.INFO))


# ----------------------
# Lambda Handler
# ----------------------

def lambda_handler(event, context):
    """
    Get user's order history
    Route: GET /api/orders/auth
    """
    try:
        # Get userId from JWT authorizer
        user_id = get_user_id(event)
        if not user_id:
            return error_response(401, 'Unauthorized')
    
        # Query orders using UserOrdersIndex GSI
        response = orders_table.query(
            IndexName='UserOrdersIndex',
            KeyConditionExpression=Key('userId').eq(user_id),
            ScanIndexForward=False  # Sort by createdAt descending (newest first)
        )

        orders = response.get('Items', [])

        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = orders_table.query(
                IndexName='UserOrdersIndex',
                KeyConditionExpression=Key('userId').eq(user_id),
                ScanIndexForward=False,
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            orders.extend(response.get('Items', []))
        
        # Format orders for frontend
        formatted_orders = []
        for order in orders:
            formatted_order = format_order(order)
            formatted_orders.append(formatted_order)

        return success_response({
            'orders': formatted_orders,
            'count': len(formatted_orders)
        })
        
    except Exception as e:
        logger.error(f'Error: {str(e)}')
        return error_response(500, f'Internal server error: {str(e)}')


# ----------------------
# Helper Functions
# ----------------------

def format_order(order):
    """Format order for frontend consumption"""
    return {
        'orderId': order['orderId'],
        'userId': order['userId'],
        'items': order.get('items', {}),
        'shipping': float(order.get('shipping', 0)),
        'tax': float(order.get('tax', 0)),
        'subtotal': float(order.get('subtotal', 0)),
        'totalAmount': float(order.get('totalAmount', 0)),
        'status': order.get('status', 'NONE'),
        'shippingAddress': order.get('shippingAddress', {}),
        'paymentProvider': order.get('paymentProvider', ''),
        'paymentRef': order.get('paymentRef', ''),
        'paymentInfo': order.get('paymentInfo', {}),
        'createdAt': order.get('createdAt', ''),
        'updatedAt': order.get('updatedAt', '')
    }