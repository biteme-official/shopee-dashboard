"""
Shopee Dashboard Runner
- collector로 데이터 수집 -> dashboard로 HTML 생성 -> 브라우저 오픈
"""
import sys
import os
import webbrowser
from collector import run_collection
from dashboard import generate_dashboard


def main():
    days = 90
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            pass

    print(f"=== Shopee Dashboard Generator (Last {days} days) ===\n")

    json_path = run_collection(days_back=days)
    if not json_path:
        print("\n[FAIL] Data collection failed. Check your shopee_tokens.json")
        return

    html_path = generate_dashboard(json_path)
    abs_path = os.path.abspath(html_path)

    print(f"\n=== Complete ===")
    print(f"Data: {json_path}")
    print(f"Dashboard: {abs_path}")

    webbrowser.open(f"file:///{abs_path}")


if __name__ == "__main__":
    main()
