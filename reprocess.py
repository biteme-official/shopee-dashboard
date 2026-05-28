import json, pandas as pd
from collector import calculate_metrics
from dashboard import generate_dashboard

with open("output/shopee_data_20260528.json", encoding="utf-8") as f:
    data = json.load(f)

orders = data["orders"]
escrow = data["escrow"]

df_orders = pd.DataFrame(orders)
if 'buyer_payment_info_shipping_fee' not in df_orders.columns:
    df_escrow = pd.DataFrame(escrow)
    df_orders = df_orders.merge(df_escrow, on="order_sn", how="left")
df = calculate_metrics(df_orders)
data["orders"] = json.loads(df.fillna(0).to_json(orient="records"))

with open("output/shopee_data_20260528.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, default=str)

generate_dashboard("output/shopee_data_20260528.json", "output/shopee_dashboard_20260528.html")
print("Done")
