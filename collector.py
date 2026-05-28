"""
Shopee API Data Collector
- 상품/주문/정산/환불 데이터 수집
- JSON으로 저장하여 대시보드 생성기에 전달
"""
import hmac
import hashlib
import time
import os
import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from config import PARTNER_ID, PARTNER_KEY, SHOP_ID, HOST, TOKEN_FILE

KST = timezone(timedelta(hours=9))


def make_sign(path, timestamp, access_token=None, shop_id=None):
    if access_token and shop_id:
        base_str = f"{PARTNER_ID}{path}{timestamp}{access_token}{shop_id}"
    else:
        base_str = f"{PARTNER_ID}{path}{timestamp}"
    return hmac.new(PARTNER_KEY.encode(), base_str.encode(), hashlib.sha256).hexdigest()


def get_valid_access_token():
    try:
        with open(TOKEN_FILE, 'r') as f:
            tokens = json.load(f)
    except FileNotFoundError:
        tokens_json = os.environ.get('SHOPEE_TOKENS_JSON', '')
        if not tokens_json:
            print("[ERROR] shopee_tokens.json not found and SHOPEE_TOKENS_JSON not set")
            return None
        tokens = json.loads(tokens_json.lstrip('﻿').strip())
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(tokens, f)
        print(f"[TOKEN] Created {TOKEN_FILE} from env var")

    now = int(time.time())
    if now > (tokens.get('expire_time', 0) - 600):
        print("[TOKEN] Refreshing...")
        path = "/api/v2/auth/access_token/get"
        sign = make_sign(path, now)
        url = f"{HOST}{path}?partner_id={PARTNER_ID}&timestamp={now}&sign={sign}"
        payload = {"refresh_token": tokens['refresh_token'], "partner_id": PARTNER_ID, "shop_id": SHOP_ID}
        res = requests.post(url, json=payload).json()
        if 'access_token' in res:
            tokens = {
                "access_token": res['access_token'],
                "refresh_token": res['refresh_token'],
                "expire_time": now + res['expire_in']
            }
            with open(TOKEN_FILE, 'w') as f:
                json.dump(tokens, f)
            print("[TOKEN] Refreshed OK")
        else:
            print("[ERROR] Token refresh failed:", res)
            return None
    return tokens['access_token']


def api_get(path, access_token, extra_params=None):
    t = int(time.time())
    sign = make_sign(path, t, access_token, SHOP_ID)
    params = {
        "partner_id": PARTNER_ID,
        "timestamp": t,
        "sign": sign,
        "access_token": access_token,
        "shop_id": SHOP_ID,
    }
    if extra_params:
        params.update(extra_params)
    res = requests.get(f"{HOST}{path}", params=params).json()
    time.sleep(0.3)
    return res


def collect_products(access_token):
    print("[1/9] Collecting products...")
    path = "/api/v2/product/get_item_list"
    all_item_ids = []
    cursor = ""
    has_next = True
    time_from = int(time.time()) - (365 * 24 * 60 * 60)
    time_to = int(time.time())

    offset = 0
    while has_next:
        t = int(time.time())
        sign = make_sign(path, t, access_token, SHOP_ID)
        params = {
            "partner_id": PARTNER_ID,
            "timestamp": t,
            "sign": sign,
            "access_token": access_token,
            "shop_id": SHOP_ID,
            "offset": offset,
            "update_time_from": time_from,
            "update_time_to": time_to,
            "page_size": 100,
            "item_status": ["NORMAL", "BANNED", "UNLIST"],
        }
        res = requests.get(f"{HOST}{path}", params=params).json()
        time.sleep(0.3)
        if 'response' in res and 'item' in res['response']:
            items = res['response']['item']
            all_item_ids.extend([str(i['item_id']) for i in items])
            has_next = res['response'].get('more', False)
            offset = len(all_item_ids)
        else:
            break

    print(f"  -> {len(all_item_ids)} items found")

    # Base info
    base_path = "/api/v2/product/get_item_base_info"
    all_base = []
    for i in range(0, len(all_item_ids), 50):
        chunk = all_item_ids[i:i+50]
        res = api_get(base_path, access_token, {"item_id_list": ",".join(chunk)})
        if 'response' in res:
            for item in res['response'].get('item_list', []):
                p_info = item.get('price_info', [{}])
                if isinstance(p_info, list) and p_info:
                    p_info = p_info[0]
                elif not isinstance(p_info, dict):
                    p_info = {}
                all_base.append({
                    'item_id': str(item.get('item_id')),
                    'item_status': item.get('item_status'),
                    'item_name': item.get('item_name'),
                    'item_sku': item.get('item_sku', ''),
                    'original_price': p_info.get('original_price', 0),
                    'current_price': p_info.get('current_price', 0),
                })

    # Model info
    model_path = "/api/v2/product/get_model_list"
    all_models = []
    for item_id in all_item_ids:
        res = api_get(model_path, access_token, {"item_id": item_id})
        if res.get('error') == "" and res.get('response', {}).get('model'):
            for m in res['response']['model']:
                m_price = m.get('price_info', [{}])
                if isinstance(m_price, list) and m_price:
                    m_price = m_price[0]
                elif not isinstance(m_price, dict):
                    m_price = {}
                stock_info = m.get('stock_info_v2', {})
                if isinstance(stock_info, list) and stock_info:
                    stock_info = stock_info[0]
                elif not isinstance(stock_info, dict):
                    stock_info = {}
                all_models.append({
                    'item_id': str(item_id),
                    'model_name': m.get('model_name', ''),
                    'model_sku': m.get('model_sku', ''),
                    'model_price': m_price.get('current_price', 0),
                    'stock': stock_info.get('current_stock', 0),
                })
        else:
            all_models.append({'item_id': str(item_id), 'model_name': '', 'model_sku': '', 'model_price': 0, 'stock': 0})
        time.sleep(0.2)

    print(f"  -> {len(all_base)} base, {len(all_models)} models")
    return {'base': all_base, 'models': all_models}


def collect_orders(access_token, days_back=30):
    print(f"[2/9] Collecting orders (last {days_back} days)...")
    day_seconds = 24 * 60 * 60
    kst_offset = 9 * 60 * 60
    now = int(time.time())
    today_midnight = now - ((now + kst_offset) % day_seconds)

    all_order_sns = []

    # Shopee API allows max 15-day range per call
    for period_start in range(days_back, 0, -15):
        period_end = max(period_start - 15, 0)
        time_from = today_midnight - (day_seconds * period_start)
        time_to = today_midnight - (day_seconds * period_end)

        cursor = ""
        has_next = True
        while has_next:
            res = api_get("/api/v2/order/get_order_list", access_token, {
                "time_range_field": "create_time",
                "time_from": time_from,
                "time_to": time_to,
                "page_size": 100,
                "cursor": cursor
            })
            if 'response' in res and 'order_list' in res['response']:
                orders = res['response']['order_list']
                all_order_sns.extend([o['order_sn'] for o in orders])
                has_next = res['response'].get('more', False)
                cursor = res['response'].get('next_cursor', "")
            else:
                break

    print(f"  -> {len(all_order_sns)} orders found")
    if not all_order_sns:
        return []

    # Order details
    detail_path = "/api/v2/order/get_order_detail"
    optional_fields = "buyer_user_id,buyer_username,actual_shipping_fee,item_list,pay_time,shipping_carrier,payment_method"
    all_details = []

    for i in range(0, len(all_order_sns), 50):
        chunk = all_order_sns[i:i+50]
        res = api_get(detail_path, access_token, {
            "order_sn_list": ",".join(chunk),
            "response_optional_fields": optional_fields
        })
        if 'response' in res and 'order_list' in res['response']:
            all_details.extend(res['response']['order_list'])

    # Flatten to item level
    rows = []
    for order in all_details:
        order_sn = order.get('order_sn')
        order_status = order.get('order_status')
        create_time = order.get('create_time', 0)
        pay_time = order.get('pay_time', 0)
        payment_method = order.get('payment_method', '')
        buyer_username = order.get('buyer_username', '')

        for item in order.get('item_list', []):
            rows.append({
                'order_sn': order_sn,
                'order_status': order_status,
                'create_time': create_time,
                'pay_time': pay_time,
                'payment_method': payment_method,
                'buyer_username': buyer_username,
                'item_id': str(item.get('item_id')),
                'item_name': item.get('item_name', ''),
                'model_name': item.get('model_name', ''),
                'model_sku': item.get('model_sku', ''),
                'original_price': item.get('model_original_price', 0),
                'discounted_price': item.get('model_discounted_price', 0),
                'quantity': item.get('model_quantity_purchased', 0),
            })

    print(f"  -> {len(rows)} line items")
    return rows


def collect_escrow(access_token, order_sns):
    print(f"[3/9] Collecting escrow for {len(order_sns)} orders...")
    escrow_path = "/api/v2/payment/get_escrow_detail"
    results = []

    for sn in order_sns:
        res = api_get(escrow_path, access_token, {"order_sn": sn})
        if 'response' in res:
            r = res['response']
            order_income = r.get('order_income', {})
            buyer_payment = r.get('buyer_payment_info', {})
            results.append({
                'order_sn': r.get('order_sn', sn),
                'escrow_amount': order_income.get('escrow_amount', 0),
                'commission_fee': order_income.get('commission_fee', 0),
                'service_fee': order_income.get('service_fee', 0),
                'seller_transaction_fee': order_income.get('seller_transaction_fee', 0),
                'final_product_gst': order_income.get('final_escrow_product_gst', 0),
                'final_shipping_gst': order_income.get('final_escrow_shipping_gst', 0),
                'actual_shipping_fee': order_income.get('actual_shipping_fee', 0),
                'shipping_rebate': order_income.get('shopee_shipping_rebate', 0),
                'buyer_shipping_fee': buyer_payment.get('shipping_fee', 0),
            })
        time.sleep(0.2)

    print(f"  -> {len(results)} escrow records")
    return results


def collect_returns(access_token):
    print("[4/9] Collecting returns...")
    res = api_get("/api/v2/returns/get_return_list", access_token, {
        "page_no": 1,
        "page_size": 100
    })
    returns_list = res.get('response', {}).get('return_list', [])
    results = []
    for r in returns_list:
        results.append({
            'order_sn': r.get('order_sn'),
            'return_sn': r.get('return_sn'),
            'status': r.get('status'),
            'reason': r.get('reason', ''),
            'refund_amount': r.get('refund_amount', 0),
            'create_time': r.get('create_time', 0),
        })
    print(f"  -> {len(results)} returns")
    return results


def collect_item_extra_info(access_token, item_ids):
    """상품별 조회수, 좋아요수 수집"""
    print(f"[5/9] Collecting item extra info (views/likes)...")
    path = "/api/v2/product/get_item_extra_info"
    results = []

    for item_id in item_ids:
        res = api_get(path, access_token, {"item_id_list": item_id})
        if 'response' in res:
            for item in res['response'].get('item_list', []):
                results.append({
                    'item_id': str(item.get('item_id')),
                    'views': item.get('views', 0),
                    'likes': item.get('likes', 0),
                    'rating_star': item.get('rating_star', 0),
                    'comment_count': item.get('comment_count', 0),
                    'sale': item.get('sale', 0),
                })
        time.sleep(0.2)

    print(f"  -> {len(results)} items with extra info")
    return results


def collect_discounts(access_token):
    """진행중/예정 할인 캠페인 수집"""
    print("[6/9] Collecting discount campaigns...")
    path = "/api/v2/discount/get_discount_list"
    results = []

    for status in ['ongoing', 'upcoming', 'expired']:
        page = 0
        has_more = True
        while has_more:
            res = api_get(path, access_token, {
                "discount_status": status,
                "page_no": page,
                "page_size": 100,
            })
            if 'response' in res:
                discounts = res['response'].get('discount_list', [])
                for d in discounts:
                    results.append({
                        'discount_id': d.get('discount_id'),
                        'discount_name': d.get('discount_name', ''),
                        'status': status,
                        'start_time': d.get('start_time', 0),
                        'end_time': d.get('end_time', 0),
                    })
                has_more = res['response'].get('more', False)
                page += 1
            else:
                break

    print(f"  -> {len(results)} discount campaigns")
    return results


def collect_shop_performance(access_token):
    """셀러 운영 건강도 지표 수집"""
    print("[7/9] Collecting shop performance...")
    res = api_get('/api/v2/account_health/get_shop_performance', access_token)
    if res.get('error') == '' and 'response' in res:
        r = res['response']
        overall = r.get('overall_performance', {})
        metrics = {}
        for m in r.get('metric_list', []):
            metrics[m['metric_name']] = {
                'current': m.get('current_period'),
                'last': m.get('last_period'),
                'target': m.get('target'),
            }
        result = {'overall': overall, 'metrics': metrics}
        print(f"  -> {len(metrics)} metrics")
        return result
    print("  -> failed")
    return None


def collect_comments(access_token, limit=100):
    """최근 리뷰/코멘트 수집"""
    print("[8/9] Collecting comments...")
    path = "/api/v2/product/get_comment"
    results = []
    cursor = 0

    while len(results) < limit:
        page_size = min(50, limit - len(results))
        res = api_get(path, access_token, {
            "item_id": 0,
            "comment_id": 0,
            "page_size": page_size,
            "cursor": cursor,
        })
        if res.get('error') == '' and 'response' in res:
            comments = res['response'].get('item_comment_list', [])
            if not comments:
                break
            for c in comments:
                results.append({
                    'comment_id': c.get('comment_id'),
                    'order_sn': c.get('order_sn', ''),
                    'item_id': str(c.get('item_id', '')),
                    'buyer_username': c.get('buyer_username', ''),
                    'rating_star': c.get('rating_star', 0),
                    'comment': c.get('comment', ''),
                    'create_time': c.get('create_time', 0),
                })
            if not res['response'].get('has_more', False):
                break
            cursor = results[-1]['comment_id']
        else:
            break

    print(f"  -> {len(results)} comments")
    return results


def save_snapshot(item_extra):
    """item_extra_info 일별 스냅샷 저장 (누적값 → 일별 delta 계산용)"""
    snapshot_file = "output/shopee_snapshots.json"
    today = datetime.now(KST).strftime('%Y-%m-%d')

    try:
        with open(snapshot_file, 'r', encoding='utf-8') as f:
            snapshots = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        snapshots = {}

    entry = {}
    for item in item_extra:
        entry[str(item['item_id'])] = {
            'views': item.get('views', 0),
            'likes': item.get('likes', 0),
            'sale': item.get('sale', 0),
        }
    snapshots[today] = entry

    with open(snapshot_file, 'w', encoding='utf-8') as f:
        json.dump(snapshots, f, ensure_ascii=False)
    print(f"  -> Snapshot saved for {today} ({len(entry)} items)")


def collect_vouchers(access_token):
    """바우처 목록 수집"""
    print("[9/9] Collecting vouchers...")
    path = "/api/v2/voucher/get_voucher_list"
    results = []

    for status in ['ongoing', 'upcoming', 'expired']:
        page = 0
        has_more = True
        while has_more:
            res = api_get(path, access_token, {
                "status": status,
                "page_no": page,
                "page_size": 100,
            })
            if 'response' in res:
                vouchers = res['response'].get('voucher_list', [])
                for v in vouchers:
                    results.append({
                        'voucher_id': v.get('voucher_id'),
                        'voucher_name': v.get('voucher_name', ''),
                        'voucher_code': v.get('voucher_code', ''),
                        'status': status,
                        'discount_amount': v.get('discount_amount', 0),
                        'min_basket_price': v.get('min_basket_price', 0),
                        'start_time': v.get('start_time', 0),
                        'end_time': v.get('end_time', 0),
                        'current_usage': v.get('current_usage', 0),
                        'usage_limit': v.get('usage_limit', 0),
                    })
                has_more = res['response'].get('more', False)
                page += 1
            else:
                break

    print(f"  -> {len(results)} vouchers")
    return results


def run_collection(days_back=30):
    access_token = get_valid_access_token()
    if not access_token:
        return None

    products = collect_products(access_token)
    orders = collect_orders(access_token, days_back)
    order_sns = list(set(row['order_sn'] for row in orders))
    escrow = collect_escrow(access_token, order_sns)
    returns = collect_returns(access_token)

    item_ids = [p['item_id'] for p in products.get('base', [])]
    item_extra = collect_item_extra_info(access_token, item_ids)
    save_snapshot(item_extra)
    discounts = collect_discounts(access_token)
    shop_perf = collect_shop_performance(access_token)
    comments = collect_comments(access_token)
    vouchers = collect_vouchers(access_token)

    # Load snapshot history for daily deltas
    snapshot_file = "output/shopee_snapshots.json"
    try:
        with open(snapshot_file, 'r', encoding='utf-8') as f:
            snapshots = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        snapshots = {}

    data = {
        'collected_at': datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S'),
        'days_back': days_back,
        'products': products,
        'orders': orders,
        'escrow': escrow,
        'returns': returns,
        'item_extra': item_extra,
        'snapshots': snapshots,
        'shop_performance': shop_perf,
        'comments': comments,
        'discounts': discounts,
        'vouchers': vouchers,
    }

    output_file = f"output/shopee_data_{datetime.now(KST).strftime('%Y%m%d')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, default=str)

    print(f"\n[DONE] Saved to {output_file}")
    return output_file


if __name__ == "__main__":
    run_collection(days_back=30)
