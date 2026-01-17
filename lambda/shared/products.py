# PRODUCTS.PY

import os
import logging

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, log_level, logging.INFO))


# ----------------------
# Product Functions
# ----------------------

def get_product(product_id, products_table):
    """Fetch product from DynamoDB"""
    try:
        response = products_table.get_item(Key={'productId': product_id})
        return response.get('Item')
    except Exception as e:
        logger.error(f'Error fetching product: {str(e)}')
        return None