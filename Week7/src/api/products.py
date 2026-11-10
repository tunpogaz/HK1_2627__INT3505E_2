from flask import Blueprint, jsonify, request
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Product
from ..errors import Conflict, NotFound, OutOfStock, BadRequest
from .schemas import ProductOut, ProductIn, ProductPatch, ReserveIn

products_bp = Blueprint("products", __name__, url_prefix="/api/v1/products")

@products_bp.get("")
def list_products():
    """Lấy danh sách sản phẩm có phân trang (Slide 24, 27)."""
    try:
        page = max(1, int(request.args.get("page", 1)))
        size = min(100, max(1, int(request.args.get("size", 20))))
    except (ValueError, TypeError):
        page, size = 1, 20

    base = db.select(Product).where(Product.archived.is_(False))
    rows = db.session.execute(
        base.order_by(Product.id).offset((page - 1) * size).limit(size)
    ).scalars().all()

    total = db.session.scalar(
        db.select(db.func.count()).select_from(Product).where(Product.archived.is_(False))
    ) or 0

    return jsonify({
        "items": [ProductOut().dump(p) for p in rows],
        "page": page,
        "size": size,
        "total": total
    }), 200

@products_bp.get("/<int:id>")
def get_product(id):
    """Lấy chi tiết 1 sản phẩm theo ID (Slide 24, 27)."""
    p = db.session.get(Product, id)
    if not p or p.archived:
        raise NotFound(message=f"Product with id {id} not found")
    return jsonify(ProductOut().dump(p)), 200

@products_bp.post("")
def create_product():
    """Tạo mới sản phẩm (Slide 24, 28)."""
    if not request.is_json:
        raise BadRequest(message="Request content-type must be application/json")

    try:
        body = ProductIn().load(request.json or {})
    except ValidationError as err:
        return jsonify({"code": "validation_error", "message": "Validation failed", "errors": err.messages}), 422

    p = Product(**body)
    db.session.add(p)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise Conflict(message="SKU already exists")

    return jsonify(ProductOut().dump(p)), 201

@products_bp.post("/<int:id>/reserve")
def reserve_product(id):
    """Đặt trước tồn kho sản phẩm (Slide 24, 28, 30)."""
    p = db.session.get(Product, id)
    if not p or p.archived:
        raise NotFound(message=f"Product with id {id} not found")

    try:
        body = ReserveIn().load(request.json or {})
    except ValidationError as err:
        return jsonify({"code": "validation_error", "message": "Validation failed", "errors": err.messages}), 422

    qty = body["qty"]
    if p.qty_in_stock < qty:
        raise OutOfStock(message=f"Only {p.qty_in_stock} items left in stock, requested {qty}")

    p.qty_in_stock -= qty
    db.session.commit()
    return jsonify(ProductOut().dump(p)), 200

@products_bp.patch("/<int:id>")
def patch_product(id):
    """Cập nhật một phần thuộc tính sản phẩm (Slide 24, 28)."""
    p = db.session.get(Product, id)
    if not p or p.archived:
        raise NotFound(message=f"Product with id {id} not found")

    try:
        body = ProductPatch().load(request.json or {}, partial=True)
    except ValidationError as err:
        return jsonify({"code": "validation_error", "message": "Validation failed", "errors": err.messages}), 422

    for k, v in body.items():
        if hasattr(p, k) and v is not None:
            setattr(p, k, v)

    db.session.commit()
    return jsonify(ProductOut().dump(p)), 200

@products_bp.delete("/<int:id>")
def delete_product(id):
    """Xóa mềm sản phẩm (soft-delete: archived=True) (Slide 24, 28)."""
    p = db.session.get(Product, id)
    if not p or p.archived:
        raise NotFound(message=f"Product with id {id} not found")

    p.archived = True
    db.session.commit()
    return "", 204

