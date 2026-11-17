#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if command -v locust &> /dev/null; then
    LOCUST_BIN="locust"
elif [ -f "../Week7/.venv/bin/locust" ]; then
    LOCUST_BIN="../Week7/.venv/bin/locust"
elif [ -f ".venv/bin/locust" ]; then
    LOCUST_BIN=".venv/bin/locust"
else
    echo "Không tìm thấy locust! Hãy kích hoạt virtualenv trước."
    exit 1
fi

mkdir -p reports

echo "Bắt đầu chạy 3 kịch bản Locust"
echo "Kịch bản A: 10 Users, spawn rate 2, thời gian 30s"
$LOCUST_BIN -f performance/locustfile.py --headless -H http://127.0.0.1:5000 \
  -u 10 -r 2 -t 30s --html reports/A.html

echo "Kịch bản B: 50 Users, spawn rate 5, thời gian 60s"
$LOCUST_BIN -f performance/locustfile.py --headless -H http://127.0.0.1:5000 \
  -u 50 -r 5 -t 60s --html reports/B.html

echo "Kịch bản C: 200 Users, spawn rate 50, thời gian 30s"
$LOCUST_BIN -f performance/locustfile.py --headless -H http://127.0.0.1:5000 \
  -u 200 -r 50 -t 30s --html reports/C.html

echo "Hoàn tất 3 kịch bản kiểm thử tải!"
echo "Báo cáo đã lưu tại: reports/A.html, reports/B.html, reports/C.html"
