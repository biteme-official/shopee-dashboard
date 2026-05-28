import json
with open("output/shopee_data_20260528.json", encoding="utf-8") as f:
    data = json.load(f)
orders = data["orders"]
sample = [o for o in orders if "net_sales_krw" in o][:3]
if sample:
    for o in sample:
        print(o.get("order_sn"), "| net_sales_krw:", o.get("net_sales_krw"), "|", type(o.get("net_sales_krw")))
else:
    print("net_sales_krw 필드 없음. 첫 번째 order 키 목록:")
    print(list(orders[0].keys()))
