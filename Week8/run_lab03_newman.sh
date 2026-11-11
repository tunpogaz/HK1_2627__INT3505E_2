#!/usr/bin/env bash
set -e

# Đảm bảo đứng ở thư mục Week8
cd "$(dirname "$0")"

echo "🚀 Đang chạy Newman cho Books API Postman Collection..."
newman run books-api.postman_collection.json \
  -e postman/local.postman_environment.json \
  -r cli,junit \
  --reporter-junit-export junit.xml

cp junit.xml reports/junit.xml 2>/dev/null || true

echo "✅ Kiểm thử Newman hoàn tất! Báo cáo lưu tại: junit.xml và reports/junit.xml"
