"""
샘플 데이터 생성 후 대시보드 HTML 열기
실제 Shopee API 없이 로컬 확인용
"""
import json
import random
import webbrowser
import os
from datetime import datetime, timedelta, timezone
from dashboard import generate_dashboard

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
random.seed(42)


def ts(dt):
    return int(dt.timestamp())


PRODUCTS_BASE = [
    {"item_id": "111001", "item_name": "바잇미 레더 크로스백 미니", "item_status": "NORMAL", "price": 39000},
    {"item_id": "111002", "item_name": "바잇미 캔버스 토트백 L", "item_status": "NORMAL", "price": 29000},
    {"item_id": "111003", "item_name": "바잇미 나일론 백팩 슬림", "item_status": "NORMAL", "price": 49000},
    {"item_id": "111004", "item_name": "바잇미 미니 파우치 지갑", "item_status": "NORMAL", "price": 19000},
    {"item_id": "111005", "item_name": "바잇미 체인백 숄더 S", "item_status": "NORMAL", "price": 55000},
]

PRODUCT_MODELS = [
    {"item_id": "111001", "model_id": "m101", "model_name": "블랙", "model_sku": "LCB-BLK", "stock": 25, "price": 39000},
    {"item_id": "111001", "model_id": "m102", "model_name": "베이지", "model_sku": "LCB-BGE", "stock": 3, "price": 39000},
    {"item_id": "111001", "model_id": "m103", "model_name": "브라운", "model_sku": "LCB-BRN", "stock": 0, "price": 39000},
    {"item_id": "111002", "model_id": "m201", "model_name": "아이보리", "model_sku": "CTL-IVR", "stock": 40, "price": 29000},
    {"item_id": "111002", "model_id": "m202", "model_name": "네이비", "model_sku": "CTL-NVY", "stock": 5, "price": 29000},
    {"item_id": "111003", "model_id": "m301", "model_name": "블랙", "model_sku": "NBP-BLK", "stock": 18, "price": 49000},
    {"item_id": "111003", "model_id": "m302", "model_name": "그레이", "model_sku": "NBP-GRY", "stock": 2, "price": 49000},
    {"item_id": "111004", "model_id": "m401", "model_name": "블랙", "model_sku": "MPW-BLK", "stock": 60, "price": 19000},
    {"item_id": "111004", "model_id": "m402", "model_name": "핑크", "model_sku": "MPW-PNK", "stock": 4, "price": 19000},
    {"item_id": "111005", "model_id": "m501", "model_name": "실버", "model_sku": "CBS-SLV", "stock": 12, "price": 55000},
    {"item_id": "111005", "model_id": "m502", "model_name": "골드", "model_sku": "CBS-GLD", "stock": 8, "price": 55000},
]

ITEM_EXTRA = [
    {"item_id": "111001", "views": 8420, "likes": 630, "rating_star": 4.7, "comment_count": 88, "sale": 215},
    {"item_id": "111002", "views": 5310, "likes": 390, "rating_star": 4.5, "comment_count": 54, "sale": 178},
    {"item_id": "111003", "views": 6780, "likes": 520, "rating_star": 4.6, "comment_count": 72, "sale": 142},
    {"item_id": "111004", "views": 3920, "likes": 280, "rating_star": 4.3, "comment_count": 41, "sale": 310},
    {"item_id": "111005", "views": 4150, "likes": 345, "rating_star": 4.8, "comment_count": 65, "sale": 98},
]

STATUSES = ["COMPLETED"] * 6 + ["SHIPPED"] * 2 + ["IN_CANCEL"] * 1 + ["TO_SHIP"] * 1
PAYMENT_METHODS = ["ShopeePay"] * 5 + ["Credit Card"] * 3 + ["Bank Transfer"] * 2
BUYERS = [f"buyer_{i:04d}" for i in range(1, 300)]

MODEL_WEIGHTS = {
    "111001": [0.5, 0.3, 0.2],
    "111002": [0.65, 0.35],
    "111003": [0.7, 0.3],
    "111004": [0.6, 0.4],
    "111005": [0.55, 0.45],
}

MODELS_BY_ITEM = {}
for m in PRODUCT_MODELS:
    MODELS_BY_ITEM.setdefault(m["item_id"], []).append(m)

RETURN_REASONS = ["Product defect", "Wrong item", "Changed mind", "Size issue", "Late delivery"]


COHORT_MONTHS = ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05']
# 코호트월별 신규 유저 풀 (겹치지 않게 구분)
COHORT_BUYERS = {
    '2026-01': [f"buyer_{i:04d}" for i in range(1,   56)],
    '2026-02': [f"buyer_{i:04d}" for i in range(56,  121)],
    '2026-03': [f"buyer_{i:04d}" for i in range(121, 196)],
    '2026-04': [f"buyer_{i:04d}" for i in range(196, 256)],
    '2026-05': [f"buyer_{i:04d}" for i in range(256, 300)],
}
# 코호트 기준 N개월 차 재구매율
RETENTION = [1.0, 0.31, 0.18, 0.12, 0.08]
HOUR_WEIGHTS = [1,1,1,1,1,1,2,3,4,5,6,6,5,6,7,7,8,8,7,6,5,4,3,2]


def random_dt_in_month(month_str):
    year, month = int(month_str[:4]), int(month_str[5:])
    month_start = datetime(year, month, 1, tzinfo=KST)
    if month < 12:
        month_end = datetime(year, month + 1, 1, tzinfo=KST) - timedelta(seconds=1)
    else:
        month_end = datetime(year, 12, 31, 23, 59, 59, tzinfo=KST)
    month_end = min(month_end, NOW)
    if month_start > NOW:
        return None
    delta_days = (month_end - month_start).days
    day_offset = random.randint(0, max(0, delta_days))
    hour = random.choices(range(24), weights=HOUR_WEIGHTS)[0]
    return month_start + timedelta(days=day_offset, hours=hour, minutes=random.randint(0, 59))


def make_single_order(sn_ref, buyer, order_dt):
    product = random.choice(PRODUCTS_BASE)
    iid = product["item_id"]
    model = random.choices(MODELS_BY_ITEM[iid], weights=MODEL_WEIGHTS[iid])[0]
    qty = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
    orig = product["price"]
    disc_pct = random.choices([0, 5, 10, 15], weights=[0.4, 0.3, 0.2, 0.1])[0]
    disc_price = int(orig * (1 - disc_pct / 100))
    order_sn = f"SG{sn_ref[0]:08d}"
    sn_ref[0] += 1
    rev = disc_price * qty
    commission = round(rev * 0.02)
    service   = round(rev * 0.01)
    txn_fee   = round(rev * 0.005)
    order = {
        "order_sn": order_sn, "item_id": iid,
        "item_name": product["item_name"], "model_id": model["model_id"],
        "model_name": model["model_name"], "model_sku": model["model_sku"],
        "quantity": qty, "original_price": orig,
        "discounted_price": disc_price if disc_pct > 0 else None,
        "create_time": ts(order_dt),
        "order_status": random.choice(STATUSES),
        "payment_method": random.choice(PAYMENT_METHODS),
        "buyer_username": buyer,
    }
    esc = {
        "order_sn": order_sn,
        "commission_fee": -commission, "service_fee": -service,
        "seller_transaction_fee": -txn_fee,
        "final_product_gst": 0, "final_shipping_gst": 0,
        "buyer_shipping_fee": 2500, "actual_shipping_fee": -3000,
        "shipping_rebate": 500,
        "escrow_amount": rev - commission - service - txn_fee + 500,
    }
    return order, esc


def make_orders():
    orders = []
    escrow = []
    sn_ref = [220001]

    # 코호트별 재구매 패턴 생성 (1월~5월)
    for cohort_month, buyers in COHORT_BUYERS.items():
        cohort_idx = COHORT_MONTHS.index(cohort_month)
        for buyer in buyers:
            for offset, month in enumerate(COHORT_MONTHS[cohort_idx:]):
                if random.random() > RETENTION[offset]:
                    continue
                order_dt = random_dt_in_month(month)
                if order_dt is None:
                    continue
                o, e = make_single_order(sn_ref, buyer, order_dt)
                orders.append(o)
                escrow.append(e)

    # 최근 30일 추가 유기적 주문 (일별 볼륨용)
    for day_offset in range(30, -1, -1):
        day_dt = NOW - timedelta(days=day_offset)
        for _ in range(random.randint(3, 10)):
            hour = random.choices(range(24), weights=HOUR_WEIGHTS)[0]
            order_dt = day_dt.replace(hour=hour, minute=random.randint(0, 59))
            o, e = make_single_order(sn_ref, random.choice(BUYERS), order_dt)
            orders.append(o)
            escrow.append(e)

    orders.sort(key=lambda x: x['create_time'])
    return orders, escrow


def make_returns(orders):
    sample = random.sample([o for o in orders if o["order_status"] == "COMPLETED"], 8)
    returns = []
    for o in sample:
        returns.append({
            "return_sn": f"RET{random.randint(10000,99999)}",
            "order_sn": o["order_sn"],
            "reason": random.choice(RETURN_REASONS),
            "status": "ACCEPTED",
            "create_time": o["create_time"] + 86400 * random.randint(1, 5),
        })
    return returns


def make_comments(orders):
    completed = [o for o in orders if o["order_status"] == "COMPLETED"]
    sample = random.sample(completed, min(30, len(completed)))
    texts = [
        "배송 빠르고 품질 좋아요!", "색상이 사진과 동일해서 만족",
        "생각보다 작지만 예뻐요", "재구매 의사 있어요 👍",
        "포장이 꼼꼼해서 좋았습니다", "퀄리티 대비 가격 합리적",
        "친구한테 선물했는데 좋아했어요", "배송이 조금 늦었지만 제품은 만족",
        "스티치가 튼튼해서 오래 쓸 수 있을 것 같아요", "디자인이 심플해서 코디하기 쉬워요",
    ]
    comments = []
    for o in sample:
        comments.append({
            "comment_id": random.randint(100000, 999999),
            "order_sn": o["order_sn"],
            "item_id": o["item_id"],
            "buyer_username": o["buyer_username"],
            "rating_star": random.choices([3, 4, 5], weights=[0.1, 0.3, 0.6])[0],
            "comment": random.choice(texts),
            "create_time": o["create_time"] + 86400 * random.randint(2, 7),
        })
    return comments


def make_snapshots():
    snapshots = {}
    base_views = {e["item_id"]: e["views"] - 300 for e in ITEM_EXTRA}
    base_likes = {e["item_id"]: e["likes"] - 50 for e in ITEM_EXTRA}
    base_sale = {e["item_id"]: e["sale"] - 40 for e in ITEM_EXTRA}
    for i in range(31):
        d = (NOW - timedelta(days=30 - i)).strftime("%Y-%m-%d")
        entry = {}
        for iid in base_views:
            entry[iid] = {
                "views": base_views[iid] + random.randint(5, 20) * i,
                "likes": base_likes[iid] + random.randint(0, 3) * i,
                "sale": base_sale[iid] + random.randint(0, 2) * i,
            }
        snapshots[d] = entry
    return snapshots


def make_shop_performance():
    return {
        "overall": {"rating": 4.7},
        "metrics": {
            "late_shipment_rate": {"current": 0.8, "last": 1.2, "target": {"comparator": "<", "value": 2.0}},
            "non_fulfillment_rate": {"current": 0.3, "last": 0.5, "target": {"comparator": "<", "value": 1.0}},
            "cancellation_rate": {"current": 1.1, "last": 1.4, "target": {"comparator": "<", "value": 3.0}},
            "return_refund_rate": {"current": 2.5, "last": 2.8, "target": {"comparator": "<", "value": 5.0}},
            "response_rate": {"current": 97.2, "last": 95.8, "target": {"comparator": ">", "value": 90.0}},
            "average_chat_response_time": {"current": 0.8, "last": 1.1, "target": {"comparator": "<", "value": 2.0}},
            "shop_rating": {"current": 4.7, "last": 4.6, "target": {"comparator": ">", "value": 4.5}},
        }
    }


orders, escrow = make_orders()
returns = make_returns(orders)
comments = make_comments(orders)
snapshots = make_snapshots()

data = {
    "collected_at": NOW.strftime("%Y-%m-%d %H:%M:%S"),
    "days_back": 143,
    "products": {"base": PRODUCTS_BASE, "models": PRODUCT_MODELS},
    "orders": orders,
    "escrow": escrow,
    "returns": returns,
    "item_extra": ITEM_EXTRA,
    "snapshots": snapshots,
    "shop_performance": make_shop_performance(),
    "comments": comments,
    "discounts": [
        {"discount_id": 9001, "discount_name": "5월 특가 세일", "status": "ongoing",
         "start_time": ts(NOW - timedelta(days=3)), "end_time": ts(NOW + timedelta(days=4))},
        {"discount_id": 9002, "discount_name": "신규회원 10% 할인", "status": "upcoming",
         "start_time": ts(NOW + timedelta(days=2)), "end_time": ts(NOW + timedelta(days=9))},
    ],
    "vouchers": [
        {"voucher_id": 8001, "voucher_name": "3000원 할인쿠폰", "voucher_code": "BITE3000",
         "status": "ongoing", "discount_amount": 3000, "min_basket_price": 30000,
         "start_time": ts(NOW - timedelta(days=7)), "end_time": ts(NOW + timedelta(days=7)),
         "current_usage": 42, "usage_limit": 100},
    ],
}

output_path = "output/shopee_sample_data.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, default=str)
print(f"[1/2] Sample data saved → {output_path}  ({len(orders)} orders)")

html_path = generate_dashboard(output_path)
abs_path = os.path.abspath(html_path)
print(f"[2/2] Dashboard generated → {abs_path}")

webbrowser.open(f"file:///{abs_path}")
print("브라우저에서 열렸습니다!")
