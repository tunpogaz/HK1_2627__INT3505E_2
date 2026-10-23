"""
Week 5: Flask Pagination API
"""

import base64
import json
from datetime import datetime, timezone
from flask import Flask, jsonify, request, abort, render_template_string
from sqlalchemy import select, func, or_, and_

from models import db, Book, Category, Author, BookAuthor, Review, User

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bookstore.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Whitelist các cột được phép sắp xếp (Slide 23, 27, 28)
ALLOWED_SORT_FIELDS = {
    "id": Book.id,
    "price": Book.price_vnd,
    "price_vnd": Book.price_vnd,
    "title": Book.title,
    "stock": Book.stock,
    "created_at": Book.created_at
}

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# Helper functions: cursor, sort and filter

def _encode_cursor(payload: dict) -> str:
    """Mã hóa payload cursor sang chuỗi Base64 URL-safe (Slide 21, 24)."""
    raw_json = json.dumps(payload, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw_json.encode("utf-8")).decode("utf-8").rstrip("=")


def _decode_cursor(token: str) -> dict:
    """Giải mã chuỗi Base64 URL-safe thành payload cursor (Slide 21, 24)."""
    if not token or not isinstance(token, str):
        raise ValueError("Cursor không được rỗng")
    pad_len = (-len(token)) % 4
    padded = token + ("=" * pad_len)
    try:
        decoded_bytes = base64.urlsafe_b64decode(padded)
        return json.loads(decoded_bytes.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Cursor token không hợp lệ hoặc bị lỗi cú pháp: {str(e)}")


def parse_sort(raw_sort: str):
    """
    Phân tích chuỗi sort đa khóa (Slide 23, 26, 27).
    Ví dụ: '-price,title' -> [price_vnd DESC, title ASC, id DESC]
    Trả về:
    - primary_key: tên thuộc tính chính (để trích xuất giá trị cho cursor)
    - primary_col: đối tượng Column chính
    - primary_desc: boolean (True nếu DESC)
    - order_by_clauses: danh sách các biểu thức SQLAlchemy order_by
    - normalized_sort: chuỗi sort chuẩn hóa
    """
    if not raw_sort:
        raw_sort = "-id"

    tokens = [t.strip() for t in raw_sort.split(",") if t.strip()]
    if not tokens:
        tokens = ["-id"]

    order_clauses = []
    primary_key = None
    primary_col = None
    primary_desc = False
    has_id_in_sort = False

    for idx, token in enumerate(tokens):
        is_desc = token.startswith("-")
        col_name = token.lstrip("-")

        if col_name not in ALLOWED_SORT_FIELDS:
            raise ValueError(
                f"Trường sắp xếp '{col_name}' không hợp lệ. "
                f"Các trường được hỗ trợ: {list(ALLOWED_SORT_FIELDS.keys())}"
            )

        col_obj = ALLOWED_SORT_FIELDS[col_name]
        order_clauses.append(col_obj.desc() if is_desc else col_obj.asc())

        if col_name == "id":
            has_id_in_sort = True

        if idx == 0:
            primary_key = col_name
            primary_col = col_obj
            primary_desc = is_desc

    if not has_id_in_sort:
        order_clauses.append(Book.id.desc() if primary_desc else Book.id.asc())

    normalized_sort = ",".join(tokens)
    return primary_key, primary_col, primary_desc, order_clauses, normalized_sort


def apply_cursor_condition(query, cursor_data: dict, current_sort: str, primary_col, primary_desc: bool):
    """
    Áp dụng điều kiện Seek Condition cho Cursor.
    Kiểm tra tính nhất quán giữa cursor token và tham số sort hiện tại.
    """
    token_sort = cursor_data.get("s")
    if token_sort != current_sort:
        return None, (
            f"Sort key trong cursor ('{token_sort}') không khớp với sort request ('{current_sort}'). "
            "Client vui lòng bắt đầu lại từ trang đầu tiên khi thay đổi thứ tự sắp xếp."
        )

    val = cursor_data.get("v")
    last_id = cursor_data.get("i")

    if last_id is None:
        return None, "Cursor payload thiếu trường định danh id 'i'"

    if primary_col.key == "created_at" and isinstance(val, str):
        try:
            val = datetime.fromisoformat(val)
        except Exception:
            pass

    # Kỹ thuật Tuple Comparison / Boolean Seek:
    # Nếu DESC: (col < val) OR (col == val AND id < last_id)
    # Nếu ASC:  (col > val) OR (col == val AND id > last_id)
    if primary_col.key == "id":
        if primary_desc:
            query = query.filter(Book.id < last_id)
        else:
            query = query.filter(Book.id > last_id)
    else:
        if primary_desc:
            seek_cond = or_(
                primary_col < val,
                and_(primary_col == val, Book.id < last_id)
            )
        else:
            seek_cond = or_(
                primary_col > val,
                and_(primary_col == val, Book.id > last_id)
            )
        query = query.filter(seek_cond)

    return query, None


# ============================================================================
# DEMO WEB UI ROUTE (Localhost Interactive Demo)
# ============================================================================

DEMO_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bookstore API - Pagination & Filtering Demo (Week 5)</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">
    <style>
        body { background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1e293b; }
        .hero { background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%); color: white; padding: 2.5rem 0; border-radius: 0 0 1.5rem 1.5rem; margin-bottom: 2rem; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
        .card { border: none; border-radius: 1rem; box-shadow: 0 2px 12px rgba(0,0,0,0.04); transition: transform 0.2s, box-shadow 0.2s; }
        .card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
        .book-card { height: 100%; display: flex; flex-direction: column; justify-content: space-between; border-left: 4px solid #0284c7; }
        .badge-genre { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; padding: 0.35rem 0.65rem; border-radius: 2rem; }
        .genre-tech { background-color: #e0f2fe; color: #0369a1; }
        .genre-science { background-color: #ecfdf5; color: #047857; }
        .genre-fiction { background-color: #fdf2f8; color: #be185d; }
        .genre-business { background-color: #fef3c7; color: #b45309; }
        .genre-history { background-color: #f3e8ff; color: #6b21a8; }
        .price-tag { font-size: 1.15rem; font-weight: 700; color: #0f172a; }
        .api-url-box { background-color: #0f172a; color: #38bdf8; font-family: SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.85rem; padding: 0.85rem 1.25rem; border-radius: 0.75rem; word-break: break-all; }
        .json-viewer { background-color: #0f172a; color: #e2e8f0; font-family: SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.8rem; padding: 1rem; border-radius: 0.75rem; max-height: 380px; overflow-y: auto; }
        .token-badge { background-color: #f1f5f9; color: #475569; font-family: monospace; padding: 0.25rem 0.5rem; border-radius: 0.35rem; font-size: 0.75rem; border: 1px dashed #cbd5e1; }
        .strategy-pill { cursor: pointer; padding: 0.6rem 1.25rem; border-radius: 2rem; font-weight: 600; transition: all 0.2s; }
        .strategy-pill.active { background-color: #1e3a8a; color: white; box-shadow: 0 2px 8px rgba(30,58,138,0.3); }
        .strategy-pill:not(.active) { background-color: #e2e8f0; color: #475569; }
    </style>
</head>
<body>

<div class="hero">
    <div class="container">
        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
            <div>
                <span class="badge bg-white text-primary mb-2 px-3 py-1 fw-bold">UET INT3505E · Kỹ thuật Hướng Dịch vụ</span>
                <h1 class="h3 fw-bold mb-1"><i class="fa-solid fa-book-open me-2"></i>Bookstore API · Phân trang & Lọc dữ liệu</h1>
                <p class="mb-0 text-white-50 small">Demo trực quan trên Localhost: So sánh <b>Offset/Limit</b> vs <b>Cursor-based</b> Pagination, Multi-key Sort & Filter</p>
            </div>
            <div class="text-end">
                <span class="badge bg-success-subtle text-success border border-success px-3 py-2">
                    <i class="fa-solid fa-circle-check me-1"></i>Server Online (Port 5000)
                </span>
                <div class="small text-white-50 mt-1">SV: Vũ Tuấn Phong - 22028258</div>
            </div>
        </div>
    </div>
</div>

<div class="container pb-5">
    <!-- Controls Section -->
    <div class="card p-4 mb-4">
        <div class="row g-3 align-items-center">
            <!-- Strategy Selector -->
            <div class="col-12 col-md-5">
                <label class="form-label fw-bold small text-muted text-uppercase mb-2">Chiến thuật phân trang</label>
                <div class="d-flex gap-2">
                    <button class="btn strategy-pill active flex-fill" id="btnCursor" onclick="setStrategy('cursor')">
                        <i class="fa-solid fa-bolt me-1"></i>Cursor-based
                    </button>
                    <button class="btn strategy-pill flex-fill" id="btnOffset" onclick="setStrategy('offset')">
                        <i class="fa-solid fa-list-ol me-1"></i>Offset / Limit
                    </button>
                </div>
            </div>

            <!-- Genre Filter -->
            <div class="col-6 col-md-3">
                <label class="form-label fw-bold small text-muted text-uppercase mb-2">Thể loại (Genre)</label>
                <select class="form-select" id="selectGenre" onchange="resetAndFetch()">
                    <option value="">-- Tất cả thể loại --</option>
                    <option value="tech">Công nghệ (tech)</option>
                    <option value="science">Khoa học (science)</option>
                    <option value="fiction">Văn học (fiction)</option>
                    <option value="business">Kinh doanh (business)</option>
                    <option value="history">Lịch sử (history)</option>
                </select>
            </div>

            <!-- Sort Multi-key -->
            <div class="col-6 col-md-4">
                <label class="form-label fw-bold small text-muted text-uppercase mb-2">Sắp xếp (Sort Whitelist)</label>
                <select class="form-select" id="selectSort" onchange="resetAndFetch()">
                    <option value="-id">Mới nhất (sort=-id)</option>
                    <option value="id">Cũ nhất (sort=id)</option>
                    <option value="price">Giá tăng dần (sort=price)</option>
                    <option value="-price">Giá giảm dần (sort=-price)</option>
                    <option value="-price,title">Đa khóa: Giá giảm + Tiêu đề A-Z (-price,title)</option>
                    <option value="title">Tựa đề A-Z (sort=title)</option>
                </select>
            </div>
        </div>

        <div class="row g-3 mt-1 align-items-center">
            <!-- Limit Selector -->
            <div class="col-6 col-md-3">
                <label class="form-label fw-bold small text-muted text-uppercase mb-2">Số lượng / trang (Limit)</label>
                <select class="form-select form-select-sm" id="selectLimit" onchange="resetAndFetch()">
                    <option value="6" selected>6 cuốn / trang</option>
                    <option value="12">12 cuốn / trang</option>
                    <option value="20">20 cuốn / trang</option>
                </select>
            </div>

            <!-- Quick Filter in_stock -->
            <div class="col-6 col-md-3">
                <label class="form-label fw-bold small text-muted text-uppercase mb-2">Tình trạng kho</label>
                <select class="form-select form-select-sm" id="selectStock" onchange="resetAndFetch()">
                    <option value="">Tất cả kho</option>
                    <option value="true">Còn hàng (in_stock=true)</option>
                </select>
            </div>

            <div class="col-12 col-md-6 text-md-end pt-3">
                <button class="btn btn-outline-primary btn-sm me-2" onclick="resetAndFetch()">
                    <i class="fa-solid fa-arrows-rotate me-1"></i>Làm mới
                </button>
                <a href="/api/v1/categories" target="_blank" class="btn btn-outline-secondary btn-sm me-2">
                    <i class="fa-solid fa-tags me-1"></i>/api/v1/categories
                </a>
                <button class="btn btn-outline-dark btn-sm" type="button" data-bs-toggle="collapse" data-bs-target="#jsonCollapse">
                    <i class="fa-solid fa-code me-1"></i>Xem Raw JSON
                </button>
            </div>
        </div>
    </div>

    <!-- Live API URL Bar -->
    <div class="mb-4">
        <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="small fw-bold text-muted text-uppercase"><i class="fa-solid fa-terminal me-1"></i>URL Endpoint đang gọi:</span>
            <span class="badge bg-secondary" id="latencyBadge">Response: ~ms</span>
        </div>
        <div class="api-url-box d-flex justify-content-between align-items-center">
            <span id="currentApiUrl">GET /api/v1/books</span>
            <button class="btn btn-sm btn-link text-white-50 p-0 text-decoration-none" onclick="copyUrl()" title="Copy URL">
                <i class="fa-regular fa-copy"></i>
            </button>
        </div>
    </div>

    <!-- Collapsible Raw JSON Viewer -->
    <div class="collapse mb-4" id="jsonCollapse">
        <div class="card p-3 bg-dark">
            <div class="d-flex justify-content-between text-white-50 small mb-2">
                <span><i class="fa-brands fa-js me-1"></i>Raw JSON Response Payload</span>
                <span id="responseStatus">Status: 200 OK</span>
            </div>
            <pre class="json-viewer mb-0" id="jsonOutput">// JSON response will appear here...</pre>
        </div>
    </div>

    <!-- Strategy Description Alert -->
    <div class="alert alert-info d-flex align-items-center mb-4" id="strategyExplanation">
        <i class="fa-solid fa-circle-info fs-4 me-3"></i>
        <div class="small" id="strategyInfoText">
            Đang tải dữ liệu...
        </div>
    </div>

    <!-- Books Grid Container -->
    <div class="row g-4" id="booksContainer">
        <!-- Book Cards rendered by JS -->
    </div>

    <!-- Empty State -->
    <div class="text-center py-5 d-none" id="emptyState">
        <i class="fa-solid fa-box-open fs-1 text-muted mb-3"></i>
        <h5 class="text-muted">Không tìm thấy cuốn sách nào thỏa mãn bộ lọc</h5>
    </div>

    <!-- Dynamic Pagination Footer -->
    <div class="card p-3 mt-4">
        <!-- Offset Controls -->
        <div id="offsetControls" class="d-none">
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                <div class="small text-muted" id="offsetSummary">
                    Hiển thị 1 - 6 trong tổng số 60 cuốn sách
                </div>
                <div class="d-flex align-items-center gap-2">
                    <button class="btn btn-outline-primary btn-sm px-3" id="btnPrevOffset" onclick="offsetPrev()">
                        <i class="fa-solid fa-chevron-left me-1"></i>Trang trước
                    </button>
                    <span class="badge bg-primary px-3 py-2" id="offsetPageBadge">Trang 1 / 10</span>
                    <button class="btn btn-outline-primary btn-sm px-3" id="btnNextOffset" onclick="offsetNext()">
                        Trang sau<i class="fa-solid fa-chevron-right ms-1"></i>
                    </button>
                </div>
            </div>
        </div>

        <!-- Cursor Controls -->
        <div id="cursorControls">
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                <div>
                    <span class="small text-muted d-block mb-1">Cursor hiện tại:</span>
                    <span class="token-badge" id="cursorBadge">Trang đầu (Initial Seek)</span>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-outline-secondary btn-sm" onclick="resetAndFetch()">
                        <i class="fa-solid fa-arrow-rotate-left me-1"></i>Về đầu trang
                    </button>
                    <button class="btn btn-primary btn-sm px-4 fw-bold" id="btnNextCursor" onclick="cursorNext()">
                        Tải trang tiếp theo (Next Cursor) <i class="fa-solid fa-forward-step ms-1"></i>
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
    let state = {
        strategy: 'cursor',
        limit: 6,
        offset: 0,
        currentCursor: null,
        nextCursor: null,
        hasMore: false,
        total: 0,
        currentPage: 1,
        totalPages: 1
    };

    function setStrategy(st) {
        state.strategy = st;
        document.getElementById('btnCursor').classList.toggle('active', st === 'cursor');
        document.getElementById('btnOffset').classList.toggle('active', st === 'offset');
        document.getElementById('cursorControls').classList.toggle('d-none', st !== 'cursor');
        document.getElementById('offsetControls').classList.toggle('d-none', st !== 'offset');
        resetAndFetch();
    }

    function resetAndFetch() {
        state.offset = 0;
        state.currentCursor = null;
        state.nextCursor = null;
        fetchBooks();
    }

    function offsetNext() {
        state.offset += state.limit;
        fetchBooks();
    }

    function offsetPrev() {
        state.offset = Math.max(0, state.offset - state.limit);
        fetchBooks();
    }

    function cursorNext() {
        if (!state.nextCursor) return;
        state.currentCursor = state.nextCursor;
        fetchBooks();
    }

    async function fetchBooks() {
        const genre = document.getElementById('selectGenre').value;
        const sort = document.getElementById('selectSort').value;
        const limit = parseInt(document.getElementById('selectLimit').value) || 6;
        const inStock = document.getElementById('selectStock').value;
        state.limit = limit;

        const params = new URLSearchParams();
        params.set('strategy', state.strategy);
        params.set('limit', limit);
        params.set('sort', sort);

        if (genre) params.set('genre', genre);
        if (inStock) params.set('in_stock', inStock);

        if (state.strategy === 'offset') {
            params.set('offset', state.offset);
        } else if (state.strategy === 'cursor' && state.currentCursor) {
            params.set('cursor', state.currentCursor);
        }

        const url = `/api/v1/books?${params.toString()}`;
        document.getElementById('currentApiUrl').innerText = `GET ${url}`;

        const startTime = performance.now();
        try {
            const resp = await fetch(url);
            const endTime = performance.now();
            document.getElementById('latencyBadge').innerText = `Response: ${(endTime - startTime).toFixed(0)} ms`;
            document.getElementById('responseStatus').innerText = `Status: ${resp.status} ${resp.statusText}`;

            const json = await resp.json();
            document.getElementById('jsonOutput').innerText = JSON.stringify(json, null, 2);

            if (!resp.ok) {
                alert(`Lỗi API (${resp.status}): ${json.message || json.error}`);
                return;
            }

            renderBooks(json.data || []);
            updatePaginationUI(json.pagination || {});
        } catch (err) {
            console.error(err);
            alert('Không thể kết nối đến server: ' + err.message);
        }
    }

    function renderBooks(books) {
        const container = document.getElementById('booksContainer');
        const emptyState = document.getElementById('emptyState');

        if (!books || books.length === 0) {
            container.innerHTML = '';
            emptyState.classList.remove('d-none');
            return;
        }

        emptyState.classList.add('d-none');
        container.innerHTML = books.map(b => {
            const authors = (b.authors || []).map(a => a.name).join(', ') || 'Nhiều tác giả';
            const price = b.price ? b.price.amount.toLocaleString('vi-VN') + ' đ' : 'Liên hệ';
            const genreSlug = b.genre || (b.category ? b.category.slug : 'other');
            const genreName = b.category ? b.category.name : genreSlug;

            return `
            <div class="col-12 col-md-6 col-lg-4">
                <div class="card p-3 book-card">
                    <div>
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <span class="badge badge-genre genre-${genreSlug}">${genreName}</span>
                            <span class="badge ${b.inStock ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger'} small">
                                ${b.inStock ? '<i class="fa-solid fa-check me-1"></i>Còn ' + b.stock : 'Hết hàng'}
                            </span>
                        </div>
                        <h6 class="fw-bold mb-1 text-dark" title="${b.title}">${b.title}</h6>
                        <p class="small text-muted mb-2"><i class="fa-solid fa-user-pen me-1"></i>${authors}</p>
                    </div>
                    <div class="pt-2 border-top mt-2 d-flex justify-content-between align-items-center">
                        <div>
                            <span class="small text-muted d-block" style="font-size: 0.7rem;">GIÁ BÁN</span>
                            <span class="price-tag">${price}</span>
                        </div>
                        <div class="text-end">
                            <span class="badge bg-light text-muted border font-monospace small">${b.id}</span>
                        </div>
                    </div>
                </div>
            </div>`;
        }).join('');
    }

    function updatePaginationUI(p) {
        const exp = document.getElementById('strategyInfoText');

        if (p.strategy === 'offset') {
            document.getElementById('strategyExplanation').className = 'alert alert-primary d-flex align-items-center mb-4';
            exp.innerHTML = `<b>Chiến thuật Offset / Limit:</b> Server duyệt qua <code>OFFSET ${p.offset}</code> và trả về <code>${p.limit}</code> cuốn. Phù hợp UI dạng nhảy trang (Trang <b>${p.current_page} / ${p.total_pages}</b>, Tổng: <b>${p.total}</b> cuốn).`;

            document.getElementById('offsetSummary').innerText = `Hiển thị offset ${p.offset} - ${p.offset + state.limit} / Tổng ${p.total} cuốn sách`;
            document.getElementById('offsetPageBadge').innerText = `Trang ${p.current_page} / ${p.total_pages}`;
            document.getElementById('btnPrevOffset').disabled = !p.has_prev;
            document.getElementById('btnNextOffset').disabled = !p.has_next;
        } else {
            document.getElementById('strategyExplanation').className = 'alert alert-info d-flex align-items-center mb-4';
            state.nextCursor = p.next_cursor;
            state.hasMore = p.has_more;

            document.getElementById('cursorBadge').innerText = state.currentCursor ? state.currentCursor : '(Trang đầu tiên)';
            const btnNext = document.getElementById('btnNextCursor');
            btnNext.disabled = !p.has_more;

            if (p.has_more) {
                btnNext.innerHTML = `Tải trang tiếp theo (Next Cursor) <i class="fa-solid fa-forward-step ms-1"></i>`;
                exp.innerHTML = `<b>Chiến thuật Cursor-based:</b> Sử dụng Opaque Token mã hóa giá trị cột sắp xếp & tie-breaker <code>id</code>. Đảm bảo tốc độ <b>O(1)</b> và tính nhất quán dữ liệu khi có bản ghi mới thêm vào.`;
            } else {
                btnNext.innerHTML = `Đã đến trang cuối cùng <i class="fa-solid fa-check ms-1"></i>`;
                exp.innerHTML = `<b>Đã duyệt hết toàn bộ collection!</b> Không còn bản ghi kế tiếp (<code>has_more: false</code>).`;
            }
        }
    }

    function copyUrl() {
        const text = document.getElementById('currentApiUrl').innerText.replace('GET ', window.location.origin);
        navigator.clipboard.writeText(text);
        alert('Đã copy đường dẫn URL: ' + text);
    }

    // Auto load on start
    window.addEventListener('DOMContentLoaded', () => {
        fetchBooks();
    });
</script>

</body>
</html>
"""

@app.get("/")
def demo_ui():
    """Giao diện Web tương tác trực quan kiểm thử phân trang trên Localhost."""
    return render_template_string(DEMO_HTML)


# ============================================================================
# API ROUTES
# ============================================================================

@app.get("/api/v1/books")
def list_books():
    """
    Endpoint chính lấy danh sách sách có phân trang và lọc.
    Query Parameters:
    - strategy: 'offset' | 'cursor' (mặc định: 'cursor')
    - limit: số lượng bản ghi (1 - 100, mặc định: 20)
    - offset: số bản ghi bỏ qua (chỉ dùng cho strategy=offset)
    - cursor: chuỗi base64 token (chỉ dùng cho strategy=cursor)
    - genre: lọc theo thể loại (vd: 'tech', 'science', 'fiction')
    - price_min: khoảng giá tối thiểu
    - price_max: khoảng giá tối đa
    - in_stock: true | false
    - sort: trường sắp xếp (vd: 'price', '-price', '-price,title')
    - fields: chọn trường trả về (vd: 'id,title,price')
    """
    strategy = request.args.get("strategy", "cursor").lower()
    if strategy not in ("offset", "cursor"):
        return jsonify({
            "error": "invalid_parameter",
            "message": "Strategy phân trang không hợp lệ. Chỉ chấp nhận 'offset' hoặc 'cursor'."
        }), 400
    
    try:
        limit = min(max(request.args.get("limit", DEFAULT_LIMIT, type=int), 1), MAX_LIMIT)
    except (ValueError, TypeError):
        limit = DEFAULT_LIMIT

    raw_sort = request.args.get("sort", "-id")
    try:
        p_key, p_col, p_desc, order_clauses, norm_sort = parse_sort(raw_sort)
    except ValueError as err:
        return jsonify({
            "error": "bad_sort",
            "message": str(err)
        }), 400

    query = select(Book)

    # 1. Áp dụng Filter theo Thể loại 
    genre_param = request.args.get("genre")
    if genre_param:
        genre_slug = genre_param.strip().lower()
        query = query.join(Category, Book.category_id == Category.id).filter(
            func.lower(Category.slug) == genre_slug
        )

    # 2. Áp dụng Filter theo khoảng giá và tình trạng kho 
    price_min = request.args.get("price_min", type=int)
    if price_min is not None:
        query = query.filter(Book.price_vnd >= price_min)

    price_max = request.args.get("price_max", type=int)
    if price_max is not None:
        query = query.filter(Book.price_vnd <= price_max)

    in_stock = request.args.get("in_stock")
    if in_stock is not None:
        in_stock_bool = in_stock.lower() in ("true", "1", "yes")
        if in_stock_bool:
            query = query.filter(Book.stock > 0)
        else:
            query = query.filter(Book.stock == 0)

    # Parse sparse fieldsets
    fields_arg = request.args.get("fields")
    fields = [f.strip() for f in fields_arg.split(",") if f.strip()] if fields_arg else None

    # STRATEGY 1: OFFSET / LIMIT PAGINATION
    if strategy == "offset":
        try:
            offset = max(request.args.get("offset", 0, type=int), 0)
        except (ValueError, TypeError):
            offset = 0

        # Đếm tổng số bản ghi thỏa mãn điều kiện filter
        count_stmt = select(func.count()).select_from(query.subquery())
        total = db.session.scalar(count_stmt) or 0

        # Thực thi query phân trang với offset & limit
        paged_query = query.order_by(*order_clauses).offset(offset).limit(limit)
        books = db.session.scalars(paged_query).all()

        has_next = (offset + limit) < total
        has_prev = offset > 0
        total_pages = (total + limit - 1) // limit if total > 0 else 1
        current_page = (offset // limit) + 1 if limit > 0 else 1

        return jsonify({
            "data": [b.to_dict(fields=fields) for b in books],
            "pagination": {
                "strategy": "offset",
                "offset": offset,
                "limit": limit,
                "total": total,
                "current_page": current_page,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev
            }
        }), 200

    # STRATEGY 2: CURSOR / KEYSET PAGINATION
    raw_cursor = request.args.get("cursor")
    if raw_cursor:
        try:
            cursor_data = _decode_cursor(raw_cursor)
        except ValueError as err:
            return jsonify({
                "error": "invalid_cursor",
                "message": str(err)
            }), 400

        query, err_msg = apply_cursor_condition(
            query, cursor_data, norm_sort, p_col, p_desc
        )
        if err_msg:
            return jsonify({
                "error": "cursor_validation_failed",
                "message": err_msg
            }), 400

    # Áp dụng sắp xếp và fetch với kỹ thuật limit + 1
    query = query.order_by(*order_clauses).limit(limit + 1)
    rows = db.session.scalars(query).all()

    has_more = len(rows) > limit
    items = rows[:limit]

    # Tạo next_cursor từ bản ghi cuối cùng nếu còn dữ liệu
    next_cursor = None
    if items and has_more:
        last_item = items[-1]
        raw_val = getattr(last_item, p_col.key)
        if isinstance(raw_val, datetime):
            raw_val = raw_val.isoformat()

        next_cursor = _encode_cursor({
            "s": norm_sort,
            "v": raw_val,
            "i": last_item.id
        })

    return jsonify({
        "data": [b.to_dict(fields=fields) for b in items],
        "pagination": {
            "strategy": "cursor",
            "limit": limit,
            "next_cursor": next_cursor,
            "has_more": has_more
        }
    }), 200


@app.get("/api/v1/books/<int:book_id>")
def get_book_detail(book_id: int):
    """Lấy chi tiết một cuốn sách."""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({"error": "not_found", "message": f"Không tìm thấy sách với id={book_id}"}), 404
    return jsonify(book.to_dict()), 200


@app.get("/api/v1/books/<int:book_id>/authors")
def list_book_authors(book_id: int):
    """Quan hệ N:M Nested sub-resource (Slide 11)."""
    book = db.session.get(Book, book_id)
    if not book:
        return jsonify({"error": "not_found", "message": f"Không tìm thấy sách với id={book_id}"}), 404

    rows = (
        db.session.query(Author, BookAuthor.role)
        .join(BookAuthor, Author.id == BookAuthor.author_id)
        .filter(BookAuthor.book_id == book_id)
        .all()
    )
    return jsonify([
        {"id": a.id, "name": a.name, "bio": a.bio, "role": r}
        for a, r in rows
    ]), 200


@app.get("/api/v1/categories")
def list_categories():
    """Danh mục thể loại sách."""
    categories = db.session.scalars(select(Category).order_by(Category.name)).all()
    return jsonify([c.to_dict() for c in categories]), 200

# DATABASE SEED DATA GENERATOR

def seed_database():
    """Khởi tạo dữ liệu mẫu với các thể loại, tác giả và 60 cuốn sách đa dạng."""
    db.create_all()

    if db.session.scalar(select(func.count(Book.id))) > 0:
        return

    # 1. Categories
    cats = {
        "tech": Category(name="Technology & Software", slug="tech"),
        "science": Category(name="Science & Nature", slug="science"),
        "fiction": Category(name="Fiction & Literature", slug="fiction"),
        "business": Category(name="Business & Management", slug="business"),
        "history": Category(name="History & Philosophy", slug="history")
    }
    db.session.add_all(cats.values())
    db.session.flush()

    # 2. Authors
    authors = [
        Author(name="Robert C. Martin", bio="Uncle Bob, author of Clean Code and Clean Architecture."),
        Author(name="Martin Fowler", bio="Chief Scientist at ThoughtWorks, author of Refactoring."),
        Author(name="Andrew Hunt", bio="Co-author of The Pragmatic Programmer."),
        Author(name="David Thomas", bio="Co-author of The Pragmatic Programmer."),
        Author(name="Yuval Noah Harari", bio="Historian and author of Sapiens."),
        Author(name="Carl Sagan", bio="Astronomer and science communicator."),
        Author(name="George Orwell", bio="English novelist, essayist, journalist and critic."),
        Author(name="Peter Thiel", bio="Entrepreneur and venture capitalist."),
        Author(name="Donald Knuth", bio="Author of The Art of Computer Programming.")
    ]
    db.session.add_all(authors)
    db.session.flush()

    # 3. Books data catalog
    books_data = [
        ("Clean Code: A Handbook of Agile Software Craftsmanship", "9780132350884", 450000, 25, "tech", [0]),
        ("Clean Architecture: A Craftsman's Guide", "9780134494166", 480000, 18, "tech", [0]),
        ("Refactoring: Improving the Design of Existing Code", "9780134757599", 520000, 12, "tech", [1]),
        ("Patterns of Enterprise Application Architecture", "9780321127426", 550000, 8, "tech", [1]),
        ("The Pragmatic Programmer: 20th Anniversary Edition", "9780135957059", 490000, 30, "tech", [2, 3]),
        ("Designing Data-Intensive Applications", "9781449373320", 620000, 15, "tech", [1]),
        ("The Art of Computer Programming Vol 1", "9780201896831", 850000, 5, "tech", [8]),
        ("The Art of Computer Programming Vol 2", "9780201896848", 850000, 4, "tech", [8]),
        ("The Art of Computer Programming Vol 3", "9780201896855", 850000, 6, "tech", [8]),
        ("Domain-Driven Design: Tackling Complexity", "9780321125217", 560000, 10, "tech", [1]),
        ("Site Reliability Engineering", "9781491929124", 420000, 22, "tech", [2]),
        ("Building Microservices: Designing Fine-Grained Systems", "9781492034025", 470000, 14, "tech", [1]),
        ("Test Driven Development: By Example", "9780321146533", 380000, 20, "tech", [0]),
        ("Introduction to Algorithms (CLRS)", "9780262046305", 790000, 9, "tech", [8]),
        ("Database Internals: A Deep Dive", "9781492040347", 530000, 11, "tech", [2]),

        # Science
        ("Cosmos", "9780345539434", 320000, 40, "science", [5]),
        ("Pale Blue Dot: A Vision of the Human Future", "9780345376596", 310000, 15, "science", [5]),
        ("The Demon-Haunted World: Science as a Candle", "9780345409461", 290000, 18, "science", [5]),
        ("A Brief History of Time", "9780553380163", 280000, 50, "science", [5]),
        ("The Selfish Gene", "9780199291151", 340000, 25, "science", [5]),
        ("Astrophysics for People in a Hurry", "9780393609394", 250000, 35, "science", [5]),
        ("The Elegant Universe: Superstrings and Hidden Dimensions", "9780393058581", 360000, 12, "science", [5]),
        ("What If? Serious Scientific Answers", "9780544272994", 310000, 28, "science", [5]),
        ("Six Easy Pieces: Essentials of Physics", "9780465025275", 270000, 16, "science", [8]),
        ("The Gene: An Intimate History", "9781476733524", 410000, 14, "science", [4]),

        # Fiction
        ("1984: Signet Classics Edition", "9780451524935", 180000, 60, "fiction", [6]),
        ("Animal Farm: 75th Anniversary Edition", "9780451526342", 150000, 45, "fiction", [6]),
        ("Homage to Catalonia", "9780156421171", 210000, 12, "fiction", [6]),
        ("Fahrenheit 451", "9781451673319", 195000, 30, "fiction", [6]),
        ("Brave New World", "9780060850524", 205000, 38, "fiction", [6]),
        ("The Great Gatsby", "9780743273565", 175000, 55, "fiction", [6]),
        ("To Kill a Mockingbird", "9780060935467", 190000, 42, "fiction", [6]),
        ("The Catcher in the Rye", "9780316769488", 185000, 20, "fiction", [6]),
        ("Lord of the Flies", "9780399501487", 170000, 25, "fiction", [6]),
        ("Crime and Punishment", "9780140449136", 260000, 19, "fiction", [6]),

        # Business
        ("Zero to One: Notes on Startups", "9780804139298", 290000, 50, "business", [7]),
        ("The Lean Startup: How Constant Innovation Creates Radically Successful", "9780307887894", 320000, 35, "business", [7]),
        ("Good to Great: Why Some Companies Make the Leap", "9780066620992", 350000, 28, "business", [7]),
        ("Principles: Life and Work", "9781501124020", 490000, 20, "business", [7]),
        ("Thinking, Fast and Slow", "9780374533557", 380000, 40, "business", [7]),
        ("The Hard Thing About Hard Things", "9780062273208", 340000, 18, "business", [7]),
        ("Rework", "9780307463746", 260000, 22, "business", [2, 3]),
        ("Measure What Matters", "9780525536222", 310000, 15, "business", [7]),
        ("Atomic Habits", "9780735211292", 300000, 65, "business", [7]),
        ("High Output Management", "9780679762882", 330000, 14, "business", [7]),

        # History
        ("Sapiens: A Brief History of Humankind", "9780062316097", 380000, 55, "history", [4]),
        ("Homo Deus: A Brief History of Tomorrow", "9780062464316", 390000, 40, "history", [4]),
        ("21 Lessons for the 21st Century", "9780525512172", 370000, 32, "history", [4]),
        ("Guns, Germs, and Steel", "9780393354324", 360000, 24, "history", [4]),
        ("The Silk Roads: A New History of the World", "9781101912379", 420000, 16, "history", [4]),
        ("Collapse: How Societies Choose to Fail or Succeed", "9780143117001", 350000, 10, "history", [4]),
        ("SPQR: A History of Ancient Rome", "9780871404237", 390000, 14, "history", [4]),
        ("A People's History of the United States", "9780062396587", 410000, 11, "history", [4]),
        ("Meditations by Marcus Aurelius", "9780812968255", 190000, 45, "history", [4]),
        ("The Lessons of History", "9781439149959", 220000, 30, "history", [4]),
    ]

    for title, isbn, price, stock, cat_key, author_idxs in books_data:
        bk = Book(
            title=title,
            isbn=isbn,
            price_vnd=price,
            stock=stock,
            category_id=cats[cat_key].id
        )
        for aidx in author_idxs:
            bk.authors.append(authors[aidx])
        db.session.add(bk)

    db.session.commit()
    print("Database seeded with sample books, categories, and authors!")

with app.app_context():
    seed_database()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

