"""
Shopee Dashboard Generator — biteme.co.jp/admin 스타일
3탭: 대시보드 / 퍼널 분석 / 회원 분석
프리셋 날짜 필터 + 일간/주간/월간 토글 + SectionLabel 패턴
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict

KST = timezone(timedelta(hours=9))


def load_data(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def ts_to_date(ts):
    if not ts or ts == 0: return None
    try: return datetime.fromtimestamp(int(ts), KST).strftime('%Y-%m-%d')
    except: return None

def ts_to_hour(ts):
    if not ts or ts == 0: return None
    try: return datetime.fromtimestamp(int(ts), KST).hour
    except: return None

def ts_to_weekday(ts):
    if not ts or ts == 0: return None
    try: return datetime.fromtimestamp(int(ts), KST).strftime('%a')
    except: return None


def process_data(raw):
    orders = raw.get('orders', [])
    escrow = {e['order_sn']: e for e in raw.get('escrow', [])}
    returns = raw.get('returns', [])
    products = raw.get('products', {})
    item_extra = raw.get('item_extra', [])
    discounts = raw.get('discounts', [])
    vouchers = raw.get('vouchers', [])
    snapshots = raw.get('snapshots', {})
    shop_perf = raw.get('shop_performance', None)
    comments = raw.get('comments', [])

    # === KPI ===
    total_revenue = 0
    total_orders_set = set()
    total_items_sold = 0
    total_fees = 0
    total_escrow = 0

    for o in orders:
        total_orders_set.add(o['order_sn'])
        total_revenue += (o.get('discounted_price') or o.get('original_price', 0)) * o.get('quantity', 0)
        total_items_sold += o.get('quantity', 0)

    for e in escrow.values():
        total_fees += abs(e.get('commission_fee', 0)) + abs(e.get('service_fee', 0)) + abs(e.get('seller_transaction_fee', 0))
        total_escrow += e.get('escrow_amount', 0)

    num_orders = len(total_orders_set)
    aov = total_revenue / num_orders if num_orders else 0
    fee_rate = (total_fees / total_revenue * 100) if total_revenue else 0
    refund_count = len(returns)
    refund_rate = (refund_count / num_orders * 100) if num_orders else 0

    kpi = {
        'total_revenue': round(total_revenue), 'num_orders': num_orders,
        'total_items_sold': total_items_sold, 'aov': round(aov),
        'fee_rate': round(fee_rate, 1), 'total_fees': round(total_fees),
        'total_escrow': round(total_escrow),
        'refund_count': refund_count, 'refund_rate': round(refund_rate, 1),
    }

    # === Daily timeline ===
    daily = defaultdict(lambda: {'revenue': 0, 'orders': set(), 'items': 0})
    for o in orders:
        d = ts_to_date(o.get('create_time'))
        if not d: continue
        rev = (o.get('discounted_price') or o.get('original_price', 0)) * o.get('quantity', 0)
        daily[d]['revenue'] += rev
        daily[d]['orders'].add(o['order_sn'])
        daily[d]['items'] += o.get('quantity', 0)

    timeline = []
    for d in sorted(daily.keys()):
        n_orders = len(daily[d]['orders'])
        timeline.append({
            'date': d, 'revenue': round(daily[d]['revenue']),
            'orders': n_orders, 'items': daily[d]['items'],
            'aov': round(daily[d]['revenue'] / n_orders) if n_orders else 0,
        })

    # === Order Status ===
    status_count = defaultdict(int)
    for o in orders:
        status_count[o.get('order_status', 'UNKNOWN')] += 1
    status_dist = [{'status': k, 'count': v} for k, v in sorted(status_count.items(), key=lambda x: -x[1])]

    # === Fee Breakdown ===
    fee_bd = defaultdict(float)
    for e in escrow.values():
        fee_bd['Commission'] += abs(e.get('commission_fee', 0))
        fee_bd['Service'] += abs(e.get('service_fee', 0))
        fee_bd['Transaction'] += abs(e.get('seller_transaction_fee', 0))
        fee_bd['Product GST'] += abs(e.get('final_product_gst', 0))
        fee_bd['Shipping GST'] += abs(e.get('final_shipping_gst', 0))
    fee_chart = [{'name': k, 'value': round(v)} for k, v in fee_bd.items() if v > 0]

    # === Shipping ===
    shipping = {'buyer_paid': 0, 'actual': 0, 'rebate': 0}
    for e in escrow.values():
        shipping['buyer_paid'] += e.get('buyer_shipping_fee', 0)
        shipping['actual'] += abs(e.get('actual_shipping_fee', 0))
        shipping['rebate'] += e.get('shipping_rebate', 0)

    # === Top Products (SKU perf) ===
    sku_perf = defaultdict(lambda: {'name': '', 'revenue': 0, 'quantity': 0, 'orders': set()})
    for o in orders:
        sku = o.get('model_sku') or o.get('item_id', 'unknown')
        name = o.get('item_name', '')
        model = o.get('model_name', '')
        display = f"{name} - {model}" if model else name
        rev = (o.get('discounted_price') or o.get('original_price', 0)) * o.get('quantity', 0)
        sku_perf[sku]['name'] = display
        sku_perf[sku]['revenue'] += rev
        sku_perf[sku]['quantity'] += o.get('quantity', 0)
        sku_perf[sku]['orders'].add(o['order_sn'])

    top_products = []
    for sku, v in sku_perf.items():
        top_products.append({'sku': sku, 'name': v['name'][:40], 'revenue': round(v['revenue']),
                             'quantity': v['quantity'], 'orders': len(v['orders']),
                             'avg_price': round(v['revenue']/v['quantity']) if v['quantity'] else 0})
    top_products.sort(key=lambda x: -x['revenue'])

    # === Payment ===
    pay_dist = defaultdict(int)
    seen = {}
    for o in orders:
        if o['order_sn'] not in seen:
            seen[o['order_sn']] = o.get('payment_method', 'Unknown')
    for m in seen.values(): pay_dist[m] += 1
    payment_chart = [{'method': k, 'count': v} for k, v in sorted(pay_dist.items(), key=lambda x: -x[1])]

    # === Hourly ===
    hourly = defaultdict(lambda: {'orders': set(), 'revenue': 0})
    for o in orders:
        h = ts_to_hour(o.get('create_time'))
        if h is None: continue
        rev = (o.get('discounted_price') or o.get('original_price', 0)) * o.get('quantity', 0)
        hourly[h]['orders'].add(o['order_sn'])
        hourly[h]['revenue'] += rev
    hourly_chart = [{'hour': h, 'orders': len(hourly[h]['orders']), 'revenue': round(hourly[h]['revenue'])} for h in range(24)]

    # === Low Stock ===
    base_map = {p['item_id']: p for p in products.get('base', [])}
    low_stock = []
    for m in products.get('models', []):
        iid = m.get('item_id', '')
        base = base_map.get(iid, {})
        if m.get('stock', 0) <= 5 and base.get('item_status') == 'NORMAL':
            low_stock.append({'name': base.get('item_name','')[:30], 'variant': m.get('model_name',''), 'stock': m.get('stock',0)})
    low_stock.sort(key=lambda x: x['stock'])

    product_status = defaultdict(int)
    for p in products.get('base', []):
        product_status[p.get('item_status', 'UNKNOWN')] += 1

    # === Return reasons ===
    return_reasons = defaultdict(int)
    for r in returns: return_reasons[r.get('reason','Unknown')] += 1
    return_chart = [{'reason': k, 'count': v} for k, v in sorted(return_reasons.items(), key=lambda x: -x[1])]

    # === Item Extra (views/likes) — Funnel ===
    extra_map = {e['item_id']: e for e in item_extra}
    item_funnel = []
    for base in products.get('base', []):
        iid = base['item_id']
        extra = extra_map.get(iid, {})
        views = extra.get('views', 0)
        likes = extra.get('likes', 0)
        sold = sum(o.get('quantity',0) for o in orders if o.get('item_id') == iid)
        rev = sum((o.get('discounted_price') or o.get('original_price',0)) * o.get('quantity',0) for o in orders if o.get('item_id') == iid)
        conv = round(sold / views * 100, 2) if views else 0
        item_funnel.append({'item_id': iid, 'name': base.get('item_name','')[:35], 'views': views,
                            'likes': likes, 'sold': sold, 'revenue': round(rev), 'conv_rate': conv,
                            'rating': extra.get('rating_star', 0), 'sale': extra.get('sale', 0)})
    item_funnel.sort(key=lambda x: -x['views'])

    total_views = sum(i['views'] for i in item_funnel)
    total_likes = sum(i['likes'] for i in item_funnel)
    overall_conv = round(total_items_sold / total_views * 100, 2) if total_views else 0

    # === Snapshot deltas: daily views/likes/sale per item ===
    sorted_dates = sorted(snapshots.keys())
    daily_deltas = {}
    for i in range(1, len(sorted_dates)):
        prev_date = sorted_dates[i-1]
        curr_date = sorted_dates[i]
        prev_snap = snapshots[prev_date]
        curr_snap = snapshots[curr_date]
        day_delta = {}
        for iid in curr_snap:
            pv = prev_snap.get(iid, {})
            cv = curr_snap[iid]
            dv = max(0, cv.get('views', 0) - pv.get('views', 0))
            dl = max(0, cv.get('likes', 0) - pv.get('likes', 0))
            ds = max(0, cv.get('sale', 0) - pv.get('sale', 0))
            if dv > 0 or dl > 0 or ds > 0:
                day_delta[iid] = {'views': dv, 'likes': dl, 'sale': ds}
        if day_delta:
            daily_deltas[curr_date] = day_delta

    # === Shop Performance ===
    shop_health = None
    if shop_perf:
        shop_health = {
            'overall_rating': shop_perf.get('overall', {}).get('rating', 0),
            'metrics': []
        }
        name_map = {
            'late_shipment_rate': '발송 지연율',
            'non_fulfillment_rate': '미이행률',
            'cancellation_rate': '취소율',
            'return_refund_rate': '반품/환불률',
            'preparation_time': '준비 시간(일)',
            'response_rate': '채팅 응답률',
            'average_chat_response_time': '평균 응답시간(시간)',
            'shop_rating': '숍 평점',
            'csat_rate': '고객 만족도',
            'same_day_handover_rate': '당일 인도율',
        }
        for name, label in name_map.items():
            m = shop_perf.get('metrics', {}).get(name, {})
            if m.get('current') is not None:
                target = m.get('target', {})
                target_str = f"{target.get('comparator','')} {target.get('value','')}" if target else ''
                shop_health['metrics'].append({
                    'name': label, 'current': m['current'],
                    'last': m.get('last'), 'target': target_str,
                })

    # === Comments (recent reviews) ===
    comment_list = []
    for c in comments[:30]:
        d = ts_to_date(c.get('create_time'))
        comment_list.append({
            'date': d or '',
            'buyer': c.get('buyer_username', '')[:15],
            'rating': c.get('rating_star', 0),
            'comment': c.get('comment', '')[:100],
            'item_id': c.get('item_id', ''),
        })

    # === Customer Analysis ===
    buyer_orders = defaultdict(list)
    for o in orders:
        buyer = o.get('buyer_username','') or str(o.get('buyer_user_id',''))
        if buyer: buyer_orders[buyer].append(o)

    total_buyers = len(buyer_orders)
    repeat_buyers = sum(1 for b, ords in buyer_orders.items() if len(set(o['order_sn'] for o in ords)) > 1)
    new_buyers = total_buyers - repeat_buyers
    repeat_rate = round(repeat_buyers / total_buyers * 100, 1) if total_buyers else 0

    repeat_revenue = 0; new_revenue = 0
    for buyer, ords in buyer_orders.items():
        n = len(set(o['order_sn'] for o in ords))
        rev = sum((o.get('discounted_price') or o.get('original_price',0)) * o.get('quantity',0) for o in ords)
        if n > 1: repeat_revenue += rev
        else: new_revenue += rev

    segments = {'0_no_order': 0, '1_one': 0, '2_two_three': 0, '3_four_plus': 0}
    for buyer, ords in buyer_orders.items():
        n = len(set(o['order_sn'] for o in ords))
        if n == 1: segments['1_one'] += 1
        elif n <= 3: segments['2_two_three'] += 1
        else: segments['3_four_plus'] += 1

    top_buyers = []
    for buyer, ords in buyer_orders.items():
        n = len(set(o['order_sn'] for o in ords))
        if n > 1:
            rev = sum((o.get('discounted_price') or o.get('original_price',0)) * o.get('quantity',0) for o in ords)
            top_buyers.append({'buyer': buyer[:20], 'orders': n, 'items': sum(o.get('quantity',0) for o in ords), 'revenue': round(rev)})
    top_buyers.sort(key=lambda x: -x['revenue'])

    customer = {
        'total_buyers': total_buyers, 'new_buyers': new_buyers, 'repeat_buyers': repeat_buyers,
        'repeat_rate': repeat_rate, 'repeat_revenue': round(repeat_revenue), 'new_revenue': round(new_revenue),
        'segments': [
            {'name': '1회 구매', 'value': segments['1_one'], 'color': '#fdb997'},
            {'name': '2~3회', 'value': segments['2_two_three'], 'color': '#fb8c5a'},
            {'name': '4회 이상', 'value': segments['3_four_plus'], 'color': '#f85a24'},
        ],
        'top_buyers': top_buyers[:15],
    }

    # === Cross-sell ===
    order_items = defaultdict(list)
    for o in orders: order_items[o['order_sn']].append(o.get('item_name',''))
    pair_count = defaultdict(int)
    for sn, items in order_items.items():
        unique = list(set(items))
        if len(unique) >= 2:
            for i in range(len(unique)):
                for j in range(i+1, len(unique)):
                    pair = tuple(sorted([unique[i][:25], unique[j][:25]]))
                    pair_count[pair] += 1
    cross_sell = [{'pair': f"{p[0]} + {p[1]}", 'count': c} for p, c in sorted(pair_count.items(), key=lambda x: -x[1])[:10]]
    multi_item_rate = round(sum(1 for items in order_items.values() if len(set(items)) >= 2) / len(order_items) * 100, 1) if order_items else 0

    # === Discount / Vouchers ===
    discount_analysis = {'discounted': 0, 'fullprice': 0, 'disc_rev': 0, 'full_rev': 0}
    for o in orders:
        orig = o.get('original_price',0); disc = o.get('discounted_price',0); qty = o.get('quantity',0)
        if disc and disc < orig:
            discount_analysis['discounted'] += qty; discount_analysis['disc_rev'] += disc * qty
        else:
            discount_analysis['fullprice'] += qty; discount_analysis['full_rev'] += orig * qty

    active_vouchers = []
    for v in vouchers:
        if v.get('status') == 'ongoing':
            usage_rate = round(v.get('current_usage',0)/v.get('usage_limit',1)*100,1) if v.get('usage_limit') else 0
            active_vouchers.append({'name': v.get('voucher_name','')[:30] or v.get('voucher_code',''),
                                    'code': v.get('voucher_code',''), 'discount': v.get('discount_amount',0),
                                    'min_basket': v.get('min_basket_price',0), 'used': v.get('current_usage',0),
                                    'limit': v.get('usage_limit',0), 'usage_rate': usage_rate})

    # Order rows with dates for client-side re-aggregation
    order_rows = []
    for o in orders:
        d = ts_to_date(o.get('create_time'))
        h = ts_to_hour(o.get('create_time'))
        esc = escrow.get(o.get('order_sn'), {})
        order_rows.append({
            'd': d, 'h': h,
            'sn': o.get('order_sn',''),
            'st': o.get('order_status',''),
            'iid': o.get('item_id',''),
            'name': o.get('item_name','')[:35],
            'model': o.get('model_name',''),
            'sku': o.get('model_sku','') or o.get('item_id',''),
            'orig': o.get('original_price', 0),
            'disc': o.get('discounted_price', 0),
            'qty': o.get('quantity', 0),
            'pay': o.get('payment_method',''),
            'buyer': o.get('buyer_username','') or str(o.get('buyer_user_id','')),
            'comm': esc.get('commission_fee', 0),
            'svc': esc.get('service_fee', 0),
            'txn': esc.get('seller_transaction_fee', 0),
            'pgst': esc.get('final_product_gst', 0),
            'sgst': esc.get('final_shipping_gst', 0),
            'esc_amt': esc.get('escrow_amount', 0),
            'ship_buyer': esc.get('buyer_shipping_fee', 0),
            'ship_actual': esc.get('actual_shipping_fee', 0),
            'ship_rebate': esc.get('shipping_rebate', 0),
        })

    return {
        'kpi': kpi, 'timeline': timeline, 'status_dist': status_dist,
        'fee_chart': fee_chart, 'shipping': {k: round(v) for k,v in shipping.items()},
        'top_products': top_products[:50], 'payment_chart': payment_chart,
        'hourly_chart': hourly_chart, 'low_stock': low_stock[:20],
        'product_status': [{'status':k,'count':v} for k,v in product_status.items()],
        'return_chart': return_chart,
        'item_funnel': item_funnel[:30],
        'funnel_summary': {'total_views': total_views, 'total_likes': total_likes, 'overall_conv': overall_conv},
        'customer': customer, 'cross_sell': cross_sell, 'multi_item_rate': multi_item_rate,
        'discount_analysis': discount_analysis, 'active_vouchers': active_vouchers[:10],
        'active_discounts': [d for d in discounts if d.get('status')=='ongoing'][:10],
        'order_rows': order_rows,
        'daily_deltas': daily_deltas,
        'shop_health': shop_health,
        'comment_list': comment_list,
    }


def generate_html(data, collected_at):
    D = json.dumps(data, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shopee Analytics Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{--brand:#EE4D2D;--bg:#fafafa;--card:#fff;--border:#e5e7eb;--muted:#6b7280;--text:#111827}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);font-size:13px;line-height:1.5}}

/* Header */
.header{{background:var(--card);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}}
.header-inner{{max-width:1280px;margin:0 auto;padding:0 24px;height:56px;display:flex;align-items:center;justify-content:space-between}}
.logo{{font-weight:700;font-size:14px;color:var(--brand)}}
.logo span{{color:var(--muted);font-weight:400;font-size:12px;margin-left:6px}}
.header-right{{display:flex;align-items:center;gap:8px}}

/* Range buttons */
.range-group{{display:flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;font-size:12px}}
.range-btn{{padding:6px 14px;cursor:pointer;color:var(--muted);transition:all .15s;border:none;background:var(--card)}}
.range-btn:hover{{color:var(--text)}}
.range-btn.active{{background:var(--brand);color:#fff;font-weight:600}}

/* Date picker */
.date-picker{{display:flex;align-items:center;gap:6px;font-size:12px}}
.date-input{{border:1px solid var(--border);border-radius:6px;padding:5px 10px;font-size:12px;color:var(--text)}}
.date-apply{{background:var(--brand);color:#fff;border:none;border-radius:6px;padding:5px 12px;font-size:11px;font-weight:600;cursor:pointer}}

.refresh-btn{{font-size:12px;padding:6px 14px;border:1px solid var(--border);border-radius:8px;cursor:pointer;background:var(--card);color:var(--muted)}}
.refresh-btn:hover{{color:var(--text);background:#f9fafb}}

/* Container */
.container{{max-width:1280px;margin:0 auto;padding:20px 24px}}

/* Tabs */
.tabs{{display:flex;gap:2px;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:3px;width:fit-content;margin-bottom:20px}}
.tab-btn{{padding:7px 20px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;border:none;background:transparent;color:var(--muted);transition:all .15s}}
.tab-btn:hover{{color:var(--text)}}
.tab-btn.active{{background:var(--brand);color:#fff}}
.tab-pane{{display:none}}.tab-pane.active{{display:block}}

/* Section label */
.section-label{{display:flex;align-items:center;gap:12px;margin:28px 0 16px}}
.section-label::before,.section-label::after{{content:'';flex:1;height:1px;background:var(--border)}}
.section-label span{{font-size:11px;font-weight:600;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;white-space:nowrap}}

/* KPI Cards */
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:16px}}
.kpi{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px}}
.kpi.accent{{border-color:#fed7aa;background:#fffbf5}}
.kpi .kpi-label{{font-size:11px;color:var(--muted);margin-bottom:4px}}
.kpi .kpi-value{{font-size:22px;font-weight:700;letter-spacing:-0.5px}}
.kpi.accent .kpi-value{{color:var(--brand)}}
.kpi .kpi-sub{{font-size:11px;color:var(--muted);margin-top:2px}}

/* Cards */
.card{{background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden}}
.card-header{{padding:14px 16px 10px;border-bottom:1px solid #f3f4f6}}
.card-title{{font-size:13px;font-weight:600}}
.card-desc{{font-size:11px;color:var(--muted);margin-top:2px}}
.card-body{{padding:16px}}
.card-body.no-pad{{padding:0}}

.grid-2{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}
.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}
.grid-5-3{{display:grid;grid-template-columns:2fr 3fr;gap:16px}}
.grid-3-2{{display:grid;grid-template-columns:3fr 2fr;gap:16px}}
.full{{grid-column:1/-1}}
@media(max-width:900px){{.grid-2,.grid-3,.grid-5-3,.grid-3-2{{grid-template-columns:1fr}}}}

/* Tables */
table{{width:100%;border-collapse:collapse;font-size:12px}}
thead th{{text-align:left;padding:8px 14px;font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;border-bottom:2px solid var(--border);background:#f9fafb;position:sticky;top:0}}
tbody td{{padding:8px 14px;border-bottom:1px solid #f3f4f6}}
tbody tr:hover td{{background:#f9fafb}}
.text-right{{text-align:right}}
tfoot td{{padding:8px 14px;font-weight:600;border-top:2px solid var(--border);background:#f9fafb;position:sticky;bottom:0}}

/* Toggle buttons (daily/weekly/monthly) */
.toggle-group{{display:flex;border:1px solid var(--border);border-radius:6px;overflow:hidden;font-size:11px}}
.toggle-btn{{padding:4px 12px;cursor:pointer;color:var(--muted);background:var(--card);border:none;font-weight:500;transition:all .15s}}
.toggle-btn.active{{background:var(--brand);color:#fff;font-weight:600}}

/* Funnel bar */
.funnel-step{{margin-bottom:4px}}
.funnel-meta{{display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;font-size:11px}}
.funnel-bar-bg{{height:32px;background:#f3f4f6;border-radius:6px;overflow:hidden}}
.funnel-bar-fill{{height:100%;border-radius:6px;display:flex;align-items:center;padding-left:10px;font-size:11px;color:#fff;font-weight:600;min-width:60px;transition:width .5s}}
.funnel-drop{{display:flex;align-items:center;gap:6px;padding:2px 0 2px 16px;font-size:10px;color:var(--muted)}}
.funnel-drop .drop-rate{{color:#ef4444}}

/* Mini progress bar */
.mini-bar{{display:inline-block;width:56px;height:4px;background:#f3f4f6;border-radius:2px;overflow:hidden;vertical-align:middle}}
.mini-bar-fill{{height:100%;border-radius:2px;background:var(--brand)}}

/* Badges */
.badge{{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;font-weight:600}}
.badge-red{{background:#fee2e2;color:#991b1b}}
.badge-green{{background:#d1fae5;color:#065f46}}
.badge-orange{{background:#fef3c7;color:#92400e}}

/* Stock alert */
.stock-row{{display:flex;align-items:center;gap:8px;padding:8px 14px;border-bottom:1px solid #f3f4f6;font-size:12px}}
.stock-row:last-child{{border:none}}
.stock-num{{font-weight:700;min-width:28px}}
.stock-num.zero{{color:#ef4444}}
.stock-num.low{{color:#f59e0b}}

/* Voucher card */
.voucher{{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;margin-bottom:8px}}
.voucher:last-child{{margin:0}}
.v-name{{font-weight:600;font-size:13px}}
.v-detail{{font-size:11px;color:var(--muted)}}

canvas{{max-height:260px}}
.chart-area{{position:relative}}
.scrollable{{max-height:300px;overflow-y:auto}}
.footer-note{{text-align:center;font-size:11px;color:var(--muted);padding:24px 0 8px}}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div class="header-inner">
    <div class="logo">SHOPEE<span>Analytics</span></div>
    <div class="header-right">
      <div class="range-group">
        <button class="range-btn" data-days="1">오늘</button>
        <button class="range-btn active" data-days="7">7일</button>
        <button class="range-btn" data-days="28">28일</button>
        <button class="range-btn" data-days="0">전체</button>
      </div>
      <div class="date-picker">
        <input type="date" class="date-input" id="dateFrom">
        <span style="color:var(--muted)">~</span>
        <input type="date" class="date-input" id="dateTo">
        <button class="date-apply" onclick="applyCustomDate()">적용</button>
      </div>
      <button class="refresh-btn" onclick="location.reload()">새로고침</button>
    </div>
  </div>
</div>

<div class="container">
  <!-- TABS -->
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('dashboard',this)">대시보드</button>
    <button class="tab-btn" onclick="switchTab('funnel',this)">퍼널 분석</button>
    <button class="tab-btn" onclick="switchTab('members',this)">회원 분석</button>
  </div>

  <!-- ========== TAB: 대시보드 ========== -->
  <div id="tab-dashboard" class="tab-pane active">

    <div class="section-label"><span>핵심 지표</span></div>
    <div class="kpi-grid" id="kpiArea"></div>

    <div class="section-label"><span>매출 · 주문 추이</span></div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
        <div><div class="card-title">트래픽 · 주문 · 매출 추이</div>
        <div class="card-desc">매출(막대) / 주문수(라인)</div></div>
      </div>
      <div class="card-body"><canvas id="timelineChart"></canvas></div>
    </div>

    <!-- Timeline table -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
        <div class="card-title">상세 데이터</div>
        <div class="toggle-group">
          <button class="toggle-btn active" onclick="setAgg('daily',this)">일간</button>
          <button class="toggle-btn" onclick="setAgg('weekly',this)">주간</button>
          <button class="toggle-btn" onclick="setAgg('monthly',this)">월간</button>
        </div>
      </div>
      <div class="card-body no-pad"><div class="scrollable" id="timelineTable"></div></div>
    </div>

    <div class="section-label"><span>수수료 · 배송</span></div>
    <div class="grid-2" style="margin-bottom:16px">
      <div class="card"><div class="card-header"><div class="card-title">수수료 구조</div></div><div class="card-body"><canvas id="feeChart"></canvas></div></div>
      <div class="card"><div class="card-header"><div class="card-title">배송비 정산</div></div><div class="card-body"><canvas id="shippingChart"></canvas></div></div>
    </div>

    <div class="section-label"><span>상위 상품 · 운영 현황</span></div>
    <div class="grid-5-3" style="margin-bottom:16px">
      <div class="card">
        <div class="card-header"><div class="card-title">상위 판매 상품</div></div>
        <div class="card-body no-pad"><div class="scrollable" id="topProductsTable"></div></div>
      </div>
      <div class="card">
        <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
          <div class="card-title">운영 현황</div>
          <div class="toggle-group">
            <button class="toggle-btn active" onclick="setOpsTab('lowstock',this)">재고 부족</button>
            <button class="toggle-btn" onclick="setOpsTab('status',this)">주문 상태</button>
            <button class="toggle-btn" onclick="setOpsTab('health',this)">셀러 건강도</button>
          </div>
        </div>
        <div class="card-body no-pad"><div class="scrollable" id="opsPanel"></div></div>
      </div>
    </div>

    <div class="section-label"><span>최근 리뷰</span></div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><div class="card-title">고객 리뷰</div><div class="card-desc">최근 30건</div></div>
      <div class="card-body no-pad"><div class="scrollable" id="reviewsTable"></div></div>
    </div>
  </div>

  <!-- ========== TAB: 퍼널 분석 ========== -->
  <div id="tab-funnel" class="tab-pane">

    <div id="snapshotBanner" style="display:none;margin-bottom:12px;padding:10px 16px;border-radius:8px;background:#eff6ff;border:1px solid #bfdbfe;font-size:12px;color:#1e40af"></div>

    <div class="section-label"><span>구매 전환 퍼널</span></div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><div class="card-title">Views → Likes → Purchase</div>
      <div class="card-desc">각 단계별 수량 및 전환율 (날짜 필터 적용 시 일별 스냅샷 delta 사용)</div></div>
      <div class="card-body" id="funnelArea"></div>
    </div>

    <div class="section-label"><span>상품별 전환율</span></div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><div class="card-title">상품별 조회 → 구매 전환</div>
      <div class="card-desc">조회수 높은 순 — Conv% = 판매수 / 조회수</div></div>
      <div class="card-body no-pad"><div class="scrollable" id="convTable"></div></div>
    </div>

    <div class="section-label"><span>일별 트래픽 추이</span></div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><div class="card-title">일별 조회수 · 좋아요 · 판매 추이</div>
      <div class="card-desc">스냅샷 축적 시 자동으로 데이터 증가</div></div>
      <div class="card-body"><canvas id="trafficChart"></canvas></div>
    </div>

    <div class="grid-2" style="margin-bottom:16px">
      <div class="card"><div class="card-header"><div class="card-title">시간대별 주문 분포 (KST)</div></div><div class="card-body"><canvas id="hourlyChart"></canvas></div></div>
      <div class="card"><div class="card-header"><div class="card-title">결제 수단</div></div><div class="card-body"><canvas id="paymentChart"></canvas></div></div>
    </div>

    <div class="section-label"><span>할인 · 바우처</span></div>
    <div class="grid-2" style="margin-bottom:16px">
      <div class="card"><div class="card-header"><div class="card-title">할인 vs 정가 매출</div></div><div class="card-body"><canvas id="discountChart"></canvas></div></div>
      <div class="card">
        <div class="card-header"><div class="card-title">진행중 바우처</div></div>
        <div class="card-body" id="voucherArea"></div>
      </div>
    </div>

    <div class="section-label"><span>환불 분석</span></div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><div class="card-title">환불 사유</div></div>
      <div class="card-body"><canvas id="returnChart"></canvas></div>
    </div>
  </div>

  <!-- ========== TAB: 회원 분석 ========== -->
  <div id="tab-members" class="tab-pane">

    <div class="section-label"><span>회원 핵심 지표</span></div>
    <div class="kpi-grid" id="memberKpi"></div>

    <div class="section-label"><span>구매 · 세그먼트</span></div>
    <div class="grid-2" style="margin-bottom:16px">
      <div class="card"><div class="card-header"><div class="card-title">고객 구매 횟수 분포</div></div><div class="card-body"><canvas id="segmentChart"></canvas></div></div>
      <div class="card"><div class="card-header"><div class="card-title">신규 vs 재구매 매출</div></div><div class="card-body"><canvas id="nrChart"></canvas></div></div>
    </div>

    <div class="section-label"><span>교차 구매 분석</span></div>
    <div class="grid-2" style="margin-bottom:16px">
      <div class="card">
        <div class="card-header"><div class="card-title">함께 구매한 상품 조합</div></div>
        <div class="card-body no-pad"><div class="scrollable" id="crossSellTable"></div></div>
      </div>
      <div class="card">
        <div class="card-header"><div class="card-title">Top 리피트 바이어</div></div>
        <div class="card-body no-pad"><div class="scrollable" id="topBuyersTable"></div></div>
      </div>
    </div>

    <div class="section-label"><span>SKU 전체 성과</span></div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-header"><div class="card-title">SKU Performance Table</div></div>
      <div class="card-body no-pad"><div class="scrollable" style="max-height:400px" id="skuTable"></div></div>
    </div>
  </div>

  <div class="footer-note">Shopee Partner API · Updated {collected_at}</div>
</div>

<script>
const RAW = {D};
let currentDays = 0;
let currentAgg = 'daily';
let currentOpsTab = 'lowstock';
const BRAND = '#EE4D2D';
const PAL = ['#EE4D2D','#fb8c5a','#fdb997','#94a3b8','#cbd5e1','#3b82f6','#10b981','#f59e0b'];
const fmt = n => new Intl.NumberFormat('ko-KR').format(n);
const fmtW = n => '\\u20A9' + fmt(n);

function getDateRange() {{
  if (currentDays === -1 && window._customFrom && window._customTo)
    return {{ from: window._customFrom, to: window._customTo }};
  if (currentDays === 0) return null;
  const cutoff = new Date(); cutoff.setDate(cutoff.getDate() - currentDays);
  return {{ from: cutoff.toISOString().slice(0,10), to: '9999-12-31' }};
}}

function getFilteredTimeline() {{
  const r = getDateRange();
  if (!r) return RAW.timeline;
  return RAW.timeline.filter(d => d.date >= r.from && d.date <= r.to);
}}

function getFilteredRows() {{
  const r = getDateRange();
  if (!r) return RAW.order_rows;
  return RAW.order_rows.filter(o => o.d && o.d >= r.from && o.d <= r.to);
}}

document.querySelectorAll('.range-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentDays = parseInt(btn.dataset.days);
    renderAll();
  }});
}});

function applyCustomDate() {{
  const from = document.getElementById('dateFrom').value;
  const to = document.getElementById('dateTo').value;
  if (!from || !to) return;
  document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
  currentDays = -1;
  window._customFrom = from;
  window._customTo = to;
  renderAll();
}}

function aggFromRows(rows) {{
  const rev = rows.reduce((s,o) => s + (o.disc || o.orig) * o.qty, 0);
  const sns = new Set(rows.map(o => o.sn));
  const ord = sns.size;
  const items = rows.reduce((s,o) => s + o.qty, 0);
  const aov = ord > 0 ? Math.round(rev/ord) : 0;
  const fees = rows.reduce((s,o) => s + Math.abs(o.comm) + Math.abs(o.svc) + Math.abs(o.txn), 0);
  const escrow = rows.reduce((s,o) => s + o.esc_amt, 0);
  const feeRate = rev > 0 ? (fees/rev*100).toFixed(1) : '0.0';
  return {{ rev, ord, items, aov, fees: Math.round(fees), escrow: Math.round(escrow), feeRate }};
}}

// === Tab switching ===
function switchTab(id, el) {{
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  el.classList.add('active');
}}

function setAgg(mode, el) {{
  currentAgg = mode;
  el.parentNode.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  renderTimelineTable();
}}

function setOpsTab(mode, el) {{
  currentOpsTab = mode;
  el.parentNode.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  renderOpsPanel();
}}

// === Renderers ===
let charts = {{}};
function destroyChart(id) {{ if(charts[id]) {{ charts[id].destroy(); delete charts[id]; }} }}

function renderKPI() {{
  const rows = getFilteredRows();
  const a = aggFromRows(rows);

  document.getElementById('kpiArea').innerHTML = `
    <div class="kpi accent"><div class="kpi-label">총 매출</div><div class="kpi-value">${{fmtW(Math.round(a.rev))}}</div><div class="kpi-sub">${{fmt(a.ord)}}건 주문</div></div>
    <div class="kpi accent"><div class="kpi-label">주문 수</div><div class="kpi-value">${{fmt(a.ord)}}건</div><div class="kpi-sub">${{fmt(a.items)}}개 판매</div></div>
    <div class="kpi accent"><div class="kpi-label">평균 주문금액</div><div class="kpi-value">${{fmtW(a.aov)}}</div></div>
    <div class="kpi"><div class="kpi-label">수수료율</div><div class="kpi-value">${{a.feeRate}}%</div><div class="kpi-sub">${{fmtW(a.fees)}}</div></div>
    <div class="kpi"><div class="kpi-label">에스크로</div><div class="kpi-value">${{fmtW(a.escrow)}}</div><div class="kpi-sub">수수료 후 정산</div></div>
    <div class="kpi"><div class="kpi-label">환불률</div><div class="kpi-value">${{RAW.kpi.refund_rate}}%</div><div class="kpi-sub">${{RAW.kpi.refund_count}}건</div></div>
  `;
}}

function renderTimelineChart() {{
  const tl = getFilteredTimeline();
  destroyChart('timeline');
  charts.timeline = new Chart(document.getElementById('timelineChart'), {{
    type: 'bar',
    data: {{
      labels: tl.map(d => d.date.slice(5)),
      datasets: [
        {{ label: '매출', data: tl.map(d => d.revenue), backgroundColor: BRAND+'b3', borderRadius: 3, yAxisID: 'y', order: 2 }},
        {{ label: '주문수', data: tl.map(d => d.orders), type: 'line', borderColor: '#94a3b8', pointRadius: 2, tension: .3, yAxisID: 'y1', order: 1 }},
      ]
    }},
    options: {{ responsive:true, interaction:{{mode:'index',intersect:false}},
      scales: {{ y:{{position:'left',ticks:{{callback:v=>fmt(v),font:{{size:10}}}}}}, y1:{{position:'right',grid:{{drawOnChartArea:false}},ticks:{{font:{{size:10}}}}}} }},
      plugins:{{legend:{{labels:{{font:{{size:11}}}}}}}}
    }}
  }});
}}

function renderTimelineTable() {{
  const tl = getFilteredTimeline();
  let rows;
  if (currentAgg === 'daily') {{
    rows = tl.map(d => ({{label: d.date, ...d}}));
  }} else if (currentAgg === 'weekly') {{
    const map = new Map();
    tl.forEach(d => {{
      const dt = new Date(d.date+'T00:00:00');
      const diff = dt.getDay() === 0 ? -6 : 1 - dt.getDay();
      dt.setDate(dt.getDate() + diff);
      const key = dt.toISOString().slice(0,10);
      const end = new Date(dt); end.setDate(end.getDate()+6);
      const label = key.slice(5) + '~' + end.toISOString().slice(5,10);
      if (!map.has(key)) map.set(key, {{label, revenue:0, orders:0, items:0}});
      const r = map.get(key); r.revenue += d.revenue; r.orders += d.orders; r.items += d.items;
    }});
    rows = [...map.values()];
  }} else {{
    const map = new Map();
    tl.forEach(d => {{
      const key = d.date.slice(0,7);
      if (!map.has(key)) map.set(key, {{label:key, revenue:0, orders:0, items:0}});
      const r = map.get(key); r.revenue += d.revenue; r.orders += d.orders; r.items += d.items;
    }});
    rows = [...map.values()];
  }}

  const totals = rows.reduce((a,r) => ({{revenue:a.revenue+r.revenue,orders:a.orders+r.orders,items:a.items+r.items}}), {{revenue:0,orders:0,items:0}});

  let html = '<table><thead><tr><th>날짜</th><th class="text-right">주문 수</th><th class="text-right">판매수량</th><th class="text-right">매출</th><th class="text-right">AOV</th></tr></thead><tbody>';
  rows.forEach(r => {{
    const aov = r.orders > 0 ? Math.round(r.revenue/r.orders) : 0;
    html += `<tr><td style="font-family:monospace">${{r.label}}</td><td class="text-right">${{r.orders > 0 ? r.orders+'건' : '—'}}</td><td class="text-right">${{r.items > 0 ? fmt(r.items) : '—'}}</td><td class="text-right" style="font-weight:500">${{r.revenue > 0 ? fmtW(r.revenue) : '—'}}</td><td class="text-right">${{aov > 0 ? fmtW(aov) : '—'}}</td></tr>`;
  }});
  const tAov = totals.orders > 0 ? Math.round(totals.revenue/totals.orders) : 0;
  html += `</tbody><tfoot><tr><td>합계</td><td class="text-right">${{totals.orders}}건</td><td class="text-right">${{fmt(totals.items)}}</td><td class="text-right">${{fmtW(totals.revenue)}}</td><td class="text-right">${{fmtW(tAov)}}</td></tr></tfoot></table>`;
  document.getElementById('timelineTable').innerHTML = html;
}}

function renderFeeChart() {{
  const rows = getFilteredRows();
  const seen = new Set();
  const fees = {{Commission:0, Service:0, Transaction:0, 'Product GST':0, 'Shipping GST':0}};
  rows.forEach(o => {{
    if (seen.has(o.sn)) return; seen.add(o.sn);
    fees.Commission += Math.abs(o.comm); fees.Service += Math.abs(o.svc);
    fees.Transaction += Math.abs(o.txn); fees['Product GST'] += Math.abs(o.pgst);
    fees['Shipping GST'] += Math.abs(o.sgst);
  }});
  const labels = Object.keys(fees).filter(k => fees[k] > 0);
  const vals = labels.map(k => Math.round(fees[k]));
  destroyChart('fee');
  charts.fee = new Chart(document.getElementById('feeChart'), {{
    type:'doughnut',
    data:{{labels,datasets:[{{data:vals,backgroundColor:PAL}}]}},
    options:{{plugins:{{legend:{{position:'right',labels:{{font:{{size:11}}}}}},tooltip:{{callbacks:{{label:ctx=>ctx.label+': '+fmtW(ctx.parsed)}}}}}}}}
  }});
}}

function renderShippingChart() {{
  const rows = getFilteredRows();
  const seen = new Set();
  let bp=0, ac=0, rb=0;
  rows.forEach(o => {{
    if (seen.has(o.sn)) return; seen.add(o.sn);
    bp += o.ship_buyer; ac += Math.abs(o.ship_actual); rb += o.ship_rebate;
  }});
  destroyChart('shipping');
  charts.shipping = new Chart(document.getElementById('shippingChart'), {{
    type:'bar',
    data:{{labels:['바이어 지불','실제 비용','리베이트'],datasets:[{{data:[Math.round(bp),Math.round(ac),Math.round(rb)],backgroundColor:['#3b82f6','#ef4444','#10b981'],borderRadius:6}}]}},
    options:{{indexAxis:'y',plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:ctx=>fmtW(ctx.parsed.x)}}}}}},scales:{{x:{{ticks:{{callback:v=>fmt(v),font:{{size:10}}}}}}}}}}
  }});
}}

function renderTopProducts() {{
  const rows = getFilteredRows();
  const map = new Map();
  rows.forEach(o => {{
    const key = o.sku;
    if (!map.has(key)) map.set(key, {{name:o.name+(o.model?' - '+o.model:''), revenue:0, quantity:0}});
    const e = map.get(key); e.revenue += (o.disc||o.orig)*o.qty; e.quantity += o.qty;
  }});
  const prods = [...map.entries()].map(([k,v]) => ({{...v, sku:k, revenue:Math.round(v.revenue)}})).sort((a,b) => b.revenue-a.revenue).slice(0,20);
  const maxRev = prods[0]?.revenue || 1;
  let html = '<table><thead><tr><th>상품명</th><th class="text-right">수량</th><th class="text-right">매출</th></tr></thead><tbody>';
  prods.forEach(p => {{
    html += `<tr><td><div style="display:flex;align-items:center;gap:8px"><div class="mini-bar"><div class="mini-bar-fill" style="width:${{(p.revenue/maxRev*100)}}%"></div></div><span style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block">${{p.name}}</span></div></td><td class="text-right">${{p.quantity}}개</td><td class="text-right" style="font-weight:500">${{fmtW(p.revenue)}}</td></tr>`;
  }});
  html += '</tbody></table>';
  document.getElementById('topProductsTable').innerHTML = html;
}}

function renderOpsPanel() {{
  const el = document.getElementById('opsPanel');
  if (currentOpsTab === 'lowstock') {{
    if (RAW.low_stock.length === 0) {{
      el.innerHTML = '<div style="padding:32px;text-align:center;color:var(--muted)">재고 부족 상품 없음</div>';
      return;
    }}
    let html = '';
    RAW.low_stock.forEach(s => {{
      const cls = s.stock === 0 ? 'zero' : 'low';
      const label = s.stock === 0 ? '품절' : s.stock+'개';
      html += `<div class="stock-row"><span class="stock-num ${{cls}}">${{label}}</span><span>${{s.name}}${{s.variant ? ' ('+s.variant+')' : ''}}</span></div>`;
    }});
    el.innerHTML = html;
  }} else if (currentOpsTab === 'health') {{
    const h = RAW.shop_health;
    if (!h) {{
      el.innerHTML = '<div style="padding:32px;text-align:center;color:var(--muted)">셀러 건강도 데이터 없음</div>';
      return;
    }}
    const ratingLabels = ['','🔴 위험','🟡 주의','🟢 양호','🟢 우수','🟢 최우수'];
    let html = `<div style="padding:12px 16px;background:#f0fdf4;border-bottom:1px solid #bbf7d0;font-size:12px"><b>전체 평가:</b> ${{ratingLabels[h.overall_rating]||h.overall_rating}}</div>`;
    html += '<table><thead><tr><th>지표</th><th class="text-right">현재</th><th class="text-right">이전</th><th class="text-right">목표</th></tr></thead><tbody>';
    h.metrics.forEach(m => {{
      const diff = m.last != null ? (m.current - m.last) : null;
      const diffStr = diff !== null ? (diff > 0 ? `<span style="color:#ef4444">+${{diff.toFixed(1)}}</span>` : diff < 0 ? `<span style="color:#10b981">${{diff.toFixed(1)}}</span>` : '—') : '';
      html += `<tr><td>${{m.name}}</td><td class="text-right" style="font-weight:600">${{m.current}}</td><td class="text-right">${{m.last != null ? m.last : '—'}} ${{diffStr}}</td><td class="text-right" style="color:var(--muted)">${{m.target}}</td></tr>`;
    }});
    html += '</tbody></table>';
    el.innerHTML = html;
  }} else {{
    const rows = getFilteredRows();
    const map = new Map();
    rows.forEach(o => {{ map.set(o.st, (map.get(o.st)||0)+1); }});
    const sorted = [...map.entries()].sort((a,b) => b[1]-a[1]);
    let html = '<table><thead><tr><th>주문 상태</th><th class="text-right">건수</th></tr></thead><tbody>';
    sorted.forEach(([st,cnt]) => {{ html += `<tr><td>${{st}}</td><td class="text-right">${{fmt(cnt)}}</td></tr>`; }});
    html += '</tbody></table>';
    el.innerHTML = html;
  }}
}}

function renderReviews() {{
  const el = document.getElementById('reviewsTable');
  if (!RAW.comment_list || RAW.comment_list.length === 0) {{
    el.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted)">리뷰 없음</div>';
    return;
  }}
  let html = '<table><thead><tr><th>날짜</th><th>바이어</th><th>평점</th><th>리뷰</th></tr></thead><tbody>';
  RAW.comment_list.forEach(c => {{
    const stars = c.rating > 0 ? '★'.repeat(c.rating) : '—';
    const starColor = c.rating >= 4 ? '#10b981' : c.rating >= 3 ? '#f59e0b' : '#ef4444';
    html += `<tr><td style="font-family:monospace;white-space:nowrap">${{c.date}}</td><td>${{c.buyer}}</td><td style="color:${{starColor}}">${{stars}}</td><td style="max-width:500px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{c.comment || '<span style="color:var(--muted)">—</span>'}}</td></tr>`;
  }});
  html += '</tbody></table>';
  el.innerHTML = html;
}}

// === Snapshot helpers ===
function getFilteredDeltas() {{
  const deltas = RAW.daily_deltas || {{}};
  const dates = Object.keys(deltas).sort();
  const r = getDateRange();
  if (!r) return deltas;
  const filtered = {{}};
  dates.forEach(d => {{ if (d >= r.from && d <= r.to) filtered[d] = deltas[d]; }});
  return filtered;
}}

function sumDeltas(deltas) {{
  let totalViews=0, totalLikes=0, totalSale=0;
  const itemTotals = {{}};
  Object.values(deltas).forEach(dayData => {{
    Object.entries(dayData).forEach(([iid, v]) => {{
      totalViews += v.views||0; totalLikes += v.likes||0; totalSale += v.sale||0;
      if (!itemTotals[iid]) itemTotals[iid] = {{views:0,likes:0,sale:0}};
      itemTotals[iid].views += v.views||0; itemTotals[iid].likes += v.likes||0; itemTotals[iid].sale += v.sale||0;
    }});
  }});
  return {{totalViews, totalLikes, totalSale, itemTotals}};
}}

const hasDeltas = Object.keys(RAW.daily_deltas||{{}}).length > 0;

// === Funnel tab ===
function renderSnapshotBanner() {{
  const el = document.getElementById('snapshotBanner');
  const deltaDates = Object.keys(RAW.daily_deltas||{{}}).sort();
  if (deltaDates.length > 0) {{
    el.style.display = 'block';
    el.innerHTML = `📊 스냅샷 데이터: ${{deltaDates.length}}일 축적 (${{deltaDates[0]}} ~ ${{deltaDates[deltaDates.length-1]}}). 날짜 필터 적용 시 해당 기간의 일별 조회수/좋아요 delta를 사용합니다.`;
  }} else {{
    el.style.display = 'block';
    el.innerHTML = `ℹ️ 첫 스냅샷이 저장되었습니다. 내일 수집 시부터 일별 조회수/좋아요 변화량(delta)을 계산할 수 있습니다. 현재는 누적 데이터를 표시합니다.`;
  }}
}}

function renderFunnel() {{
  renderSnapshotBanner();
  const r = getDateRange();
  const useDeltas = r && hasDeltas;
  let viewsCount, likesCount, purchaseCount;

  if (useDeltas) {{
    const d = sumDeltas(getFilteredDeltas());
    viewsCount = d.totalViews;
    likesCount = d.totalLikes;
    const rows = getFilteredRows();
    purchaseCount = rows.reduce((s,o) => s + o.qty, 0);
  }} else {{
    viewsCount = RAW.funnel_summary.total_views;
    likesCount = RAW.funnel_summary.total_likes;
    purchaseCount = RAW.kpi.total_items_sold;
  }}

  const steps = [
    {{label:'상품 조회 (Views)', count:viewsCount, color:'#3b82f6'}},
    {{label:'좋아요 (Likes)', count:likesCount, color:'#f59e0b'}},
    {{label:'구매 완료 (Purchase)', count:purchaseCount, color:'#10b981'}},
  ];
  const max = steps[0].count || 1;

  let html = '';
  if (useDeltas) html += '<div style="font-size:11px;color:#6b7280;margin-bottom:8px">📊 스냅샷 delta 기반 (필터 기간 합산)</div>';
  else if (r) html += '<div style="font-size:11px;color:#f59e0b;margin-bottom:8px">⚠ 조회수/좋아요는 누적값 (스냅샷 축적 전), 구매는 필터 적용됨</div>';

  steps.forEach((s,i) => {{
    const pct = max > 0 ? (s.count/max*100) : 0;
    const prev = i > 0 ? steps[i-1].count : null;
    if (prev !== null && prev > 0) {{
      const conv = (s.count/prev*100).toFixed(1);
      const drop = ((prev-s.count)/prev*100).toFixed(1);
      html += `<div class="funnel-drop"><div style="width:1px;height:16px;background:#d1d5db"></div><span>↓ ${{conv}}% 진입 <span class="drop-rate">(${{drop}}% 이탈)</span></span></div>`;
    }}
    html += `<div class="funnel-step"><div class="funnel-meta"><span style="font-weight:600">${{s.label}}</span><span><b>${{fmt(s.count)}}</b> (${{pct.toFixed(1)}}%)</span></div><div class="funnel-bar-bg"><div class="funnel-bar-fill" style="width:${{Math.max(pct,8)}}%;background:${{s.color}}">${{fmt(s.count)}}</div></div></div>`;
  }});
  document.getElementById('funnelArea').innerHTML = html;
}}

function renderConvTable() {{
  const r = getDateRange();
  const useDeltas = r && hasDeltas;
  const rows = getFilteredRows();

  let items;
  if (useDeltas) {{
    const d = sumDeltas(getFilteredDeltas());
    const orderByItem = {{}};
    rows.forEach(o => {{
      if (!orderByItem[o.iid]) orderByItem[o.iid] = {{name:o.name, sold:0, revenue:0}};
      orderByItem[o.iid].sold += o.qty; orderByItem[o.iid].revenue += (o.disc||o.orig)*o.qty;
    }});
    items = [];
    const allIds = new Set([...Object.keys(d.itemTotals), ...Object.keys(orderByItem)]);
    const extraMap = {{}};
    RAW.item_funnel.forEach(it => {{ extraMap[it.item_id] = it; }});
    allIds.forEach(iid => {{
      const dt = d.itemTotals[iid] || {{views:0,likes:0}};
      const oi = orderByItem[iid] || {{name:'', sold:0, revenue:0}};
      const ex = extraMap[iid] || {{}};
      const name = oi.name || ex.name || iid;
      const conv = dt.views > 0 ? (oi.sold/dt.views*100).toFixed(2) : '0.00';
      items.push({{item_id:iid, name:name, views:dt.views, likes:dt.likes, sold:oi.sold, revenue:Math.round(oi.revenue), conv_rate:parseFloat(conv), rating:ex.rating||0}});
    }});
    items.sort((a,b) => b.views - a.views);
  }} else {{
    items = RAW.item_funnel;
  }}

  let html = '<table><thead><tr><th>#</th><th>상품명</th><th class="text-right">조회수</th><th class="text-right">좋아요</th><th class="text-right">판매</th><th class="text-right">Conv%</th><th class="text-right">매출</th><th>평점</th></tr></thead><tbody>';
  items.slice(0,30).forEach((it,i) => {{
    const cls = it.conv_rate >= 2 ? 'badge-green' : it.conv_rate >= 0.5 ? 'badge-orange' : 'badge-red';
    const stars = it.rating > 0 ? '★'.repeat(Math.round(it.rating)) + ' ' + it.rating.toFixed(1) : '—';
    html += `<tr><td>${{i+1}}</td><td>${{it.name}}</td><td class="text-right">${{fmt(it.views)}}</td><td class="text-right">${{fmt(it.likes)}}</td><td class="text-right">${{it.sold}}</td><td class="text-right"><span class="badge ${{cls}}">${{it.conv_rate}}%</span></td><td class="text-right" style="font-weight:500">${{fmtW(it.revenue)}}</td><td style="font-size:11px">${{stars}}</td></tr>`;
  }});
  html += '</tbody></table>';
  document.getElementById('convTable').innerHTML = html;
}}

function renderTrafficChart() {{
  const deltas = RAW.daily_deltas || {{}};
  const dates = Object.keys(deltas).sort();
  const r = getDateRange();
  const filtered = r ? dates.filter(d => d >= r.from && d <= r.to) : dates;

  destroyChart('traffic');
  if (filtered.length === 0) {{
    document.getElementById('trafficChart').parentElement.innerHTML = '<div style="text-align:center;color:var(--muted);padding:40px">스냅샷 데이터가 2일 이상 축적되면 일별 트래픽 추이가 표시됩니다.</div>';
    return;
  }}

  const viewsData = filtered.map(d => {{
    const day = deltas[d] || {{}};
    return Object.values(day).reduce((s,v) => s + (v.views||0), 0);
  }});
  const likesData = filtered.map(d => {{
    const day = deltas[d] || {{}};
    return Object.values(day).reduce((s,v) => s + (v.likes||0), 0);
  }});

  charts.traffic = new Chart(document.getElementById('trafficChart'), {{
    type:'bar',
    data:{{
      labels: filtered.map(d => d.slice(5)),
      datasets:[
        {{label:'조회수',data:viewsData,backgroundColor:'#3b82f680',borderRadius:3,yAxisID:'y'}},
        {{label:'좋아요',data:likesData,type:'line',borderColor:'#f59e0b',pointRadius:3,tension:.3,yAxisID:'y1'}},
      ]
    }},
    options:{{responsive:true,interaction:{{mode:'index',intersect:false}},
      scales:{{y:{{position:'left',ticks:{{font:{{size:10}}}}}},y1:{{position:'right',grid:{{drawOnChartArea:false}},ticks:{{font:{{size:10}}}}}}}},
      plugins:{{legend:{{labels:{{font:{{size:11}}}}}}}}
    }}
  }});
}}

function renderHourlyChart() {{
  const rows = getFilteredRows();
  const hourly = Array.from({{length:24}}, () => ({{orders:new Set(), revenue:0}}));
  rows.forEach(o => {{
    if (o.h == null) return;
    hourly[o.h].orders.add(o.sn);
    hourly[o.h].revenue += (o.disc||o.orig)*o.qty;
  }});
  const labels = Array.from({{length:24}}, (_,i) => i+':00');
  const revData = hourly.map(h => Math.round(h.revenue));
  const ordData = hourly.map(h => h.orders.size);

  destroyChart('hourly');
  charts.hourly = new Chart(document.getElementById('hourlyChart'), {{
    type:'bar',
    data:{{
      labels,
      datasets:[
        {{label:'매출',data:revData,backgroundColor:BRAND+'80',borderRadius:3,yAxisID:'y'}},
        {{label:'주문',data:ordData,type:'line',borderColor:'#3b82f6',pointRadius:2,tension:.4,yAxisID:'y1'}},
      ]
    }},
    options:{{responsive:true,interaction:{{mode:'index',intersect:false}},
      scales:{{y:{{position:'left',ticks:{{callback:v=>fmt(v),font:{{size:10}}}}}},y1:{{position:'right',grid:{{drawOnChartArea:false}},ticks:{{font:{{size:10}}}}}}}},
      plugins:{{legend:{{labels:{{font:{{size:11}}}}}}}}
    }}
  }});
}}

function renderPaymentChart() {{
  const rows = getFilteredRows();
  const seen = new Map();
  rows.forEach(o => {{ if (!seen.has(o.sn)) seen.set(o.sn, o.pay || 'Unknown'); }});
  const map = new Map();
  seen.forEach(m => map.set(m, (map.get(m)||0)+1));
  const sorted = [...map.entries()].sort((a,b) => b[1]-a[1]);

  destroyChart('payment');
  charts.payment = new Chart(document.getElementById('paymentChart'), {{
    type:'doughnut',
    data:{{labels:sorted.map(s=>s[0]),datasets:[{{data:sorted.map(s=>s[1]),backgroundColor:PAL}}]}},
    options:{{plugins:{{legend:{{position:'right',labels:{{font:{{size:11}}}}}}}}}}
  }});
}}

function renderDiscountChart() {{
  const rows = getFilteredRows();
  let dRev=0, fRev=0;
  rows.forEach(o => {{
    if (o.disc && o.disc < o.orig) dRev += o.disc*o.qty;
    else fRev += o.orig*o.qty;
  }});

  destroyChart('discount');
  charts.discount = new Chart(document.getElementById('discountChart'), {{
    type:'doughnut',
    data:{{labels:['할인 적용','정가 판매'],datasets:[{{data:[Math.round(dRev),Math.round(fRev)],backgroundColor:[BRAND,'#10b981']}}]}},
    options:{{plugins:{{legend:{{position:'right',labels:{{font:{{size:11}}}}}},tooltip:{{callbacks:{{label:ctx=>ctx.label+': '+fmtW(Math.round(ctx.parsed))}}}}}}}}
  }});
}}

function renderVouchers() {{
  const el = document.getElementById('voucherArea');
  if (RAW.active_vouchers.length === 0) {{
    el.innerHTML = '<div style="text-align:center;color:var(--muted);padding:20px">진행중인 바우처 없음</div>';
    return;
  }}
  el.innerHTML = RAW.active_vouchers.map(v =>
    `<div class="voucher"><div><div class="v-name">${{v.name}}</div><div class="v-detail">Code: ${{v.code}} · Min ${{fmtW(v.min_basket)}} · 할인 ${{fmtW(v.discount)}}</div></div><div style="text-align:right"><div style="font-weight:700;font-size:15px">${{v.used}}/${{v.limit}}</div><div style="font-size:10px;color:var(--muted)">사용률 ${{v.usage_rate}}%</div></div></div>`
  ).join('');
}}

function renderReturnChart() {{
  destroyChart('returns');
  if (RAW.return_chart.length === 0) return;
  charts.returns = new Chart(document.getElementById('returnChart'), {{
    type:'bar',
    data:{{labels:RAW.return_chart.map(r=>r.reason),datasets:[{{data:RAW.return_chart.map(r=>r.count),backgroundColor:'#ef4444',borderRadius:4}}]}},
    options:{{indexAxis:'y',plugins:{{legend:{{display:false}}}}}}
  }});
}}

// === Members tab ===
function computeCustomer(rows) {{
  const buyers = new Map();
  rows.forEach(o => {{
    if (!o.buyer) return;
    if (!buyers.has(o.buyer)) buyers.set(o.buyer, []);
    buyers.get(o.buyer).push(o);
  }});
  const total = buyers.size;
  let repeat=0, newB=0, repRev=0, newRev=0;
  const segs = {{one:0, two_three:0, four_plus:0}};
  const topB = [];
  buyers.forEach((ords,buyer) => {{
    const sns = new Set(ords.map(o=>o.sn));
    const n = sns.size;
    const rev = ords.reduce((s,o) => s+(o.disc||o.orig)*o.qty, 0);
    if (n > 1) {{ repeat++; repRev += rev; topB.push({{buyer:buyer.slice(0,20),orders:n,items:ords.reduce((s,o)=>s+o.qty,0),revenue:Math.round(rev)}}); }}
    else {{ newB++; newRev += rev; }}
    if (n===1) segs.one++; else if (n<=3) segs.two_three++; else segs.four_plus++;
  }});
  topB.sort((a,b) => b.revenue-a.revenue);
  const repRate = total > 0 ? (repeat/total*100).toFixed(1) : '0.0';

  const orderItems = new Map();
  rows.forEach(o => {{
    if (!orderItems.has(o.sn)) orderItems.set(o.sn, []);
    orderItems.get(o.sn).push(o.name);
  }});
  let multiItem = 0;
  const pairCount = new Map();
  orderItems.forEach(items => {{
    const unique = [...new Set(items)];
    if (unique.length >= 2) {{
      multiItem++;
      for (let i=0;i<unique.length;i++) for (let j=i+1;j<unique.length;j++) {{
        const pair = [unique[i].slice(0,25),unique[j].slice(0,25)].sort().join(' + ');
        pairCount.set(pair, (pairCount.get(pair)||0)+1);
      }}
    }}
  }});
  const multiRate = orderItems.size > 0 ? (multiItem/orderItems.size*100).toFixed(1) : '0.0';
  const crossSell = [...pairCount.entries()].sort((a,b)=>b[1]-a[1]).slice(0,10);

  return {{total,repeat,newB,repRev:Math.round(repRev),newRev:Math.round(newRev),repRate,segs,topB:topB.slice(0,15),multiRate,crossSell}};
}}

function renderMemberKPI() {{
  const rows = getFilteredRows();
  const c = computeCustomer(rows);
  const a = aggFromRows(rows);
  const repRevPct = a.rev > 0 ? (c.repRev/a.rev*100).toFixed(1) : 0;
  document.getElementById('memberKpi').innerHTML = `
    <div class="kpi accent"><div class="kpi-label">총 고객 수</div><div class="kpi-value">${{fmt(c.total)}}명</div></div>
    <div class="kpi accent"><div class="kpi-label">신규 고객</div><div class="kpi-value">${{fmt(c.newB)}}명</div></div>
    <div class="kpi"><div class="kpi-label">재구매율</div><div class="kpi-value">${{c.repRate}}%</div><div class="kpi-sub">${{fmt(c.repeat)}}명 (2회 이상)</div></div>
    <div class="kpi"><div class="kpi-label">재구매 매출</div><div class="kpi-value">${{fmtW(c.repRev)}}</div><div class="kpi-sub">전체의 ${{repRevPct}}%</div></div>
    <div class="kpi"><div class="kpi-label">복수구매 주문</div><div class="kpi-value">${{c.multiRate}}%</div><div class="kpi-sub">교차판매 기회</div></div>
  `;
}}

function renderSegmentChart() {{
  const c = computeCustomer(getFilteredRows());
  const segs = [
    {{name:'1회 구매',value:c.segs.one,color:'#fdb997'}},
    {{name:'2~3회',value:c.segs.two_three,color:'#fb8c5a'}},
    {{name:'4회 이상',value:c.segs.four_plus,color:'#f85a24'}},
  ].filter(s => s.value > 0);
  destroyChart('segment');
  charts.segment = new Chart(document.getElementById('segmentChart'), {{
    type:'doughnut',
    data:{{labels:segs.map(s=>s.name),datasets:[{{data:segs.map(s=>s.value),backgroundColor:segs.map(s=>s.color)}}]}},
    options:{{plugins:{{legend:{{position:'right',labels:{{font:{{size:11}}}}}},tooltip:{{callbacks:{{label:ctx=>ctx.label+': '+fmt(ctx.parsed)+'명'}}}}}}}}
  }});
}}

function renderNRChart() {{
  const c = computeCustomer(getFilteredRows());
  destroyChart('nr');
  charts.nr = new Chart(document.getElementById('nrChart'), {{
    type:'doughnut',
    data:{{labels:['재구매 고객','신규 고객'],datasets:[{{data:[c.repRev,c.newRev],backgroundColor:['#8b5cf6','#3b82f6']}}]}},
    options:{{plugins:{{legend:{{position:'right',labels:{{font:{{size:11}}}}}},tooltip:{{callbacks:{{label:ctx=>ctx.label+': '+fmtW(ctx.parsed)}}}}}}}}
  }});
}}

function renderCrossSell() {{
  const c = computeCustomer(getFilteredRows());
  if (c.crossSell.length === 0) {{
    document.getElementById('crossSellTable').innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted)">교차구매 데이터 없음</div>';
    return;
  }}
  let html = '<table><thead><tr><th>#</th><th>상품 조합</th><th class="text-right">동시 구매</th></tr></thead><tbody>';
  c.crossSell.forEach(([pair,cnt],i) => {{
    html += `<tr><td>${{i+1}}</td><td>${{pair}}</td><td class="text-right" style="font-weight:600">${{cnt}}건</td></tr>`;
  }});
  html += '</tbody></table>';
  document.getElementById('crossSellTable').innerHTML = html;
}}

function renderTopBuyers() {{
  const c = computeCustomer(getFilteredRows());
  let html = '<table><thead><tr><th>#</th><th>바이어</th><th class="text-right">주문</th><th class="text-right">수량</th><th class="text-right">매출</th></tr></thead><tbody>';
  c.topB.slice(0,10).forEach((b,i) => {{
    html += `<tr><td>${{i+1}}</td><td>${{b.buyer}}</td><td class="text-right">${{b.orders}}</td><td class="text-right">${{b.items}}</td><td class="text-right" style="font-weight:500">${{fmtW(b.revenue)}}</td></tr>`;
  }});
  html += '</tbody></table>';
  document.getElementById('topBuyersTable').innerHTML = html;
}}

function renderSKUTable() {{
  const rows = getFilteredRows();
  const map = new Map();
  rows.forEach(o => {{
    const key = o.sku;
    if (!map.has(key)) map.set(key, {{name:o.name+(o.model?' - '+o.model:''), revenue:0, quantity:0, orders:new Set()}});
    const e = map.get(key); e.revenue += (o.disc||o.orig)*o.qty; e.quantity += o.qty; e.orders.add(o.sn);
  }});
  const prods = [...map.entries()].map(([k,v]) => ({{sku:k,name:v.name,revenue:Math.round(v.revenue),quantity:v.quantity,orders:v.orders.size,avg_price:v.quantity>0?Math.round(v.revenue/v.quantity):0}})).sort((a,b)=>b.revenue-a.revenue);
  const maxRev = prods[0]?.revenue || 1;
  let html = '<table><thead><tr><th>#</th><th>SKU</th><th>상품</th><th class="text-right">매출</th><th class="text-right">수량</th><th class="text-right">주문</th><th class="text-right">평균단가</th><th>점유율</th></tr></thead><tbody>';
  prods.slice(0,30).forEach((p,i) => {{
    const pct = maxRev > 0 ? (p.revenue/maxRev*100) : 0;
    html += `<tr><td>${{i+1}}</td><td><span class="badge" style="background:#dbeafe;color:#1e40af">${{p.sku}}</span></td><td>${{p.name}}</td><td class="text-right" style="font-weight:500">${{fmtW(p.revenue)}}</td><td class="text-right">${{p.quantity}}</td><td class="text-right">${{p.orders}}</td><td class="text-right">${{fmtW(p.avg_price)}}</td><td><div class="mini-bar" style="width:80px"><div class="mini-bar-fill" style="width:${{pct}}%"></div></div></td></tr>`;
  }});
  html += '</tbody></table>';
  document.getElementById('skuTable').innerHTML = html;
}}

function renderAll() {{
  renderKPI(); renderTimelineChart(); renderTimelineTable();
  renderFeeChart(); renderShippingChart(); renderTopProducts(); renderOpsPanel();
  renderReviews();
  renderFunnel(); renderConvTable(); renderTrafficChart();
  renderHourlyChart(); renderPaymentChart();
  renderDiscountChart(); renderVouchers(); renderReturnChart();
  renderMemberKPI(); renderSegmentChart(); renderNRChart();
  renderCrossSell(); renderTopBuyers(); renderSKUTable();
}}

renderAll();
</script>
</body>
</html>'''
    return html


def generate_dashboard(json_path, output_path=None):
    raw = load_data(json_path)
    collected_at = raw.get('collected_at', 'Unknown')
    data = process_data(raw)
    if not output_path:
        output_path = f"output/shopee_dashboard_{datetime.now(KST).strftime('%Y%m%d')}.html"
    html = generate_html(data, collected_at)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[DONE] Dashboard saved to {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dashboard.py <shopee_data_YYYYMMDD.json>")
        sys.exit(1)
    generate_dashboard(sys.argv[1])
