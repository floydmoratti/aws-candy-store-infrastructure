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

    log_debug("Fetching product from DynamoDB", function="get_product()", product_id=product_id, table="Products")

    try:
        response = products_table.get_item(Key={'productId': product_id})

        item = response.get('Item')
        if not item:
            log_debug("Product not found", function="get_product()", product_id=product_id, table="Products")
            return None

        log_debug("Product fetched from DynamoDB", function="get_product()", product_id=product_id, item=item)

        return item
    
    except Exception as e:
        logger.error(f'Error fetching product: {str(e)}')
        return None


def log_debug(msg, **data):
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("%s | %s", msg, data)
