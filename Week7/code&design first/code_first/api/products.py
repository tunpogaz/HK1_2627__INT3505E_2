from flask.views import MethodView
from flask_smorest import Blueprint
from sqlalchemy.exc import IntegrityError

from shared.extensions import db
from shared.models import Product
from shared.errors import Conflict, NotFound, OutOfStock
try:
    from code_first.schemas import (
        ProductIn,
        ProductOut,
        ProductPaginationOut,
        ProductPatch,
        ReserveIn,
        ProductQueryArgs
    )
except ImportError:
    from schemas import (
        ProductIn,
        ProductOut,
        ProductPaginationOut,
        ProductPatch,
        ReserveIn,
        ProductQueryArgs
    )

products_blp = Blueprint(
    "products",
    __name__,
    url_prefix="/api/v1/products",
    description="Operations on products using Code-First approach (Slide 11)"
)

@products_blp.route("")
class ProductList(MethodView):
    """Resource handling GET list with pagination and POST creation (Slide 11, 24, 27)."""

    @products_blp.arguments(ProductQueryArgs, location="query")
    @products_blp.response(200, ProductPaginationOut)
    def get(self, args):
        """Lấy danh sách sản phẩm có phân trang (Slide 24, 27)."""
        page = args.get("page", 1)
        size = args.get("size", 20)

        base = db.select(Product).where(Product.archived.is_(False))
        rows = db.session.execute(
            base.order_by(Product.id).offset((page - 1) * size).limit(size)
        ).scalars().all()

        total = db.session.scalar(
            db.select(db.func.count()).select_from(Product).where(Product.archived.is_(False))
        ) or 0

        return {
            "items": rows,
            "page": page,
            "size": size,
            "total": total
        }

    @products_blp.arguments(ProductIn)
    @products_blp.response(201, ProductOut)
    def post(self, data):
        """Tạo mới sản phẩm (Slide 24, 28)."""
        p = Product(**data)
        db.session.add(p)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise Conflict(message="SKU already exists")
        return p

@products_blp.route("/<int:id>")
class ProductDetail(MethodView):
    """Resource handling GET, PATCH, and DELETE for a single product (Slide 24, 27, 28)."""

    @products_blp.response(200, ProductOut)
    def get(self, id):
        """Lấy chi tiết 1 sản phẩm theo ID (Slide 24, 27)."""
        p = db.session.get(Product, id)
        if not p or p.archived:
            raise NotFound(message=f"Product with id {id} not found")
        return p

    @products_blp.arguments(ProductPatch)
    @products_blp.response(200, ProductOut)
    def patch(self, data, id):
        """Cập nhật một phần thông tin sản phẩm (Slide 24, 28)."""
        p = db.session.get(Product, id)
        if not p or p.archived:
            raise NotFound(message=f"Product with id {id} not found")

        for key, value in data.items():
            if hasattr(p, key) and value is not None:
                setattr(p, key, value)

        db.session.commit()
        return p

    @products_blp.response(204)
    def delete(self, id):
        """Xóa mềm sản phẩm (soft-delete: archived=True) (Slide 24, 28)."""
        p = db.session.get(Product, id)
        if not p or p.archived:
            raise NotFound(message=f"Product with id {id} not found")

        p.archived = True
        db.session.commit()
        return ""

@products_blp.route("/<int:id>/reserve")
class ProductReserve(MethodView):
    """Resource handling stock reservation (Slide 24, 28, 30)."""

    @products_blp.arguments(ReserveIn)
    @products_blp.response(200, ProductOut)
    def post(self, data, id):
        """Đặt trước tồn kho sản phẩm (Slide 24, 28)."""
        p = db.session.get(Product, id)
        if not p or p.archived:
            raise NotFound(message=f"Product with id {id} not found")

        qty = data["qty"]
        if p.qty_in_stock < qty:
            raise OutOfStock(message=f"Only {p.qty_in_stock} items left in stock, requested {qty}")

        p.qty_in_stock -= qty
        db.session.commit()
        return p

