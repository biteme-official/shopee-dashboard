import glob, json, os, sys, pandas as pd
from collector import calculate_metrics
from dashboard import generate_dashboard


def find_latest_data():
    files = sorted(glob.glob("output/shopee_data_*.json"), reverse=True)
    if not files:
        print("output/shopee_data_*.json 파일이 없습니다.")
        sys.exit(1)
    return files[0]


src = sys.argv[1] if len(sys.argv) > 1 else find_latest_data()
date_tag = os.path.basename(src).replace("shopee_data_", "").replace(".json", "")
dst_json = src
dst_html = f"output/shopee_dashboard_{date_tag}.html"

print(f"[INPUT]  {src}")

with open(src, encoding="utf-8") as f:
    data = json.load(f)

df_orders = pd.DataFrame(data["orders"])
if "buyer_payment_info_shipping_fee" not in df_orders.columns:
    df_orders = df_orders.merge(pd.DataFrame(data["escrow"]), on="order_sn", how="left")
df = calculate_metrics(df_orders)
data["orders"] = json.loads(df.fillna(0).to_json(orient="records"))

with open(dst_json, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, default=str)

generate_dashboard(dst_json, dst_html)
print(f"[OUTPUT] {dst_html}")
print("Done")
