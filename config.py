import os
from dotenv import load_dotenv

load_dotenv()

PARTNER_ID = int(os.environ.get("SHOPEE_PARTNER_ID", 0))
PARTNER_KEY = os.environ.get("SHOPEE_PARTNER_KEY", "")
SHOP_ID = int(os.environ.get("SHOPEE_SHOP_ID", 0))
HOST = os.environ.get("SHOPEE_HOST", "https://partner.shopeemobile.com")
TOKEN_FILE = os.environ.get("SHOPEE_TOKEN_FILE", "shopee_tokens.json")
