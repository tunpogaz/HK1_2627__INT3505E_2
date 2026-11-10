# Thư mục So sánh: Code-First & Design-First Demo (Buổi 07)

Thư mục này chứa 2 bản demo minh họa trực quan sự khác biệt giữa hai trường phái phát triển Backend API từ OpenAPI 3.0:

---

## 1. Bản chất và So sánh (Slide 6 & 12)

| Tiêu chí | Code-First (`code_first/`) | Design-First (`design_first/`) |
| :--- | :--- | :--- |
| **Bản chất** | Viết code Python (Resource, MethodView, Schema) trước, OpenAPI 3.0 spec được tự động sinh ra sau từ code. | Soạn thảo hợp đồng `openapi.yaml` trước, thư viện tự động map URL đến hàm xử lý (handler). |
| **Quy trình** | `Python Code` $\rightarrow$ `Spec / Doc` $\rightarrow$ `Swagger UI` | `openapi.yaml` $\rightarrow$ `Routes + Schemas` $\rightarrow$ `Handler Logic` |
| **Nguồn gốc hợp đồng** | Khai báo Marshmallow Schema trực tiếp trong mã nguồn Python. | File `openapi/products.yaml` độc lập, versioning riêng. |
| **Validation** | Marshmallow Schema tự động validate dữ liệu ngõ vào. | Connexion tự động validate dữ liệu theo chuẩn JSON Schema từ file YAML. |
| **Phù hợp nhất** | Team nhỏ (1–2 người), MVP, prototype nhanh, schema thay đổi liên tục. | API public, multi-team (Mobile, Web, Backend) cần chốt hợp đồng trước khi code. |

---

## 2. Cách chạy Demo trên Localhost

### Demo 1: Code-First (`flask-smorest`)
Khởi chạy:
```bash
cd "/Users/tuanphong/Downloads/KTHDV/HK1_2627__INT3505E_2/Week7/code&design first/code_first"
../../.venv/bin/python app.py
```
- **Swagger UI tự sinh**: [http://localhost:5000/swagger-ui](http://localhost:5000/swagger-ui)
- **OpenAPI JSON Spec**: [http://localhost:5000/openapi.json](http://localhost:5000/openapi.json)

### Demo 2: Design-First (`connexion`)
Khởi chạy:
```bash
cd "/Users/tuanphong/Downloads/KTHDV/HK1_2627__INT3505E_2/Week7/code&design first/design_first"
../../.venv/bin/python app.py
```
- **Swagger UI tự sinh từ YAML**: [http://localhost:5001/ui](http://localhost:5001/ui)
- **Tự động bắt lỗi giá âm**:
  ```bash
  curl -X POST http://localhost:5001/products \
    -H "Content-Type: application/json" \
    -d '{"sku": "SKU-BAD", "name": "Lỗi", "price_cents": -50}'
  # Trả về: 400 Bad Request: -50 is less than the minimum of 0
  ```

