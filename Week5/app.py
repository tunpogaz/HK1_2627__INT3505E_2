"""
Week 5: Flask Pagination API
"""

import base64
import json
from datetime import datetime, timezone
from flask import Flask, jsonify, request, abort
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


# API Routes#

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

