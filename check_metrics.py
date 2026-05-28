import pandas as pd
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
df = pd.read_csv("output/shopee_metrics_20260528.csv")

def ts_to_date(ts):
    try:
        return datetime.fromtimestamp(int(ts), KST).strftime("%Y-%m-%d")
    except:
        return None

df["order_date"] = df["create_time"].apply(ts_to_date)
day = df[df["order_date"] == "2026-05-26"]
print("orders:", day["order_sn"].nunique(), "/ line items:", len(day))
print()
cols = ["order_sn","item_name","model_name","order_status",
        "original_price","discounted_price","quantity","refund_count","actual_quantity",
        "revenue_sgd","gross_revenue_sgd","total_gross_revenue_sgd",
        "shipping_fee_sgd","seller_voucher_sgd","shopee_voucher_sgd","coins_redeemed_sgd","card_promo_sgd",
        "net_sales_sgd","net_sales_krw"]
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 400)
pd.set_option("display.max_colwidth", 25)
print(day[cols].to_string(index=False))
