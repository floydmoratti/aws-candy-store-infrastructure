# PRODUCTS-GET.PY

import boto3
import os
import logging
from boto3.dynamodb.conditions import Attr
from shared.responses import success_response, error_response

dynamodb = boto3.resource('dynamodb')

products_table_name = os.getenv('PRODUCTS_TABLE')
if not products_table_name:
    raise RuntimeError("Missing required environment variable: PRODUCTS_TABLE")
products_table = dynamodb.Table(products_table_name)

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level, logging.INFO))


# ----------------------
# Lambda Handler
# ----------------------

def lambda_handler(event, context):
    
    # Get all active products with stock information
    # Route: GET /api/products
    # Used by frontend to check stock availability and update button states
    
    try:
        # Scan for all active products
        response = products_table.scan(
            FilterExpression=Attr('isActive').eq(True)
        )

        products = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = products_table.scan(
                FilterExpression=Attr('isActive').eq(True),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            products.extend(response.get('Items', []))

        # Build response object keyed by productId
        products_dict = {}
        for product in products:
            product_id = product['productId']
            products_dict[product_id] = {
                'availableGrams': int(product.get('availableGrams', 0)),
            }
        
        return success_response(products_dict)
    
    except Exception as e:
        logger.error(f'Error: {str(e)}')
        return error_response(500, f'Internal server error: {str(e)}')
