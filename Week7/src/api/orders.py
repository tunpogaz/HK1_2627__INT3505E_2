import uuid
from flask import Blueprint, jsonify, request
from marshmallow import ValidationError
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Order, OrderItem, Product
from ..errors import NotFound, BadRequest, Conflict
from .schemas import OrderIn, OrderOut

orders_bp = Blueprint("orders", __name__, url_prefix="/api/v1/orders")

@orders_bp.get("")
def list_orders():
    """Lấy danh sách tất cả đơn hàng kèm OrderItem bằng eager loading (selectinload) (Slide 20, 21, 42)."""
    stmt = db.select(Order).options(
        selectinload(Order.items).selectinload(OrderItem.product)
    ).order_by(Order.id)

    orders = db.session.execute(stmt).scalars().all()
    return jsonify(OrderOut(many=True).dump(orders)), 200

@orders_bp.get("/<int:id>")
def get_order(id):
    """Lấy chi tiết 1 đơn hàng theo ID kèm eager loading OrderItems."""
    stmt = db.select(Order).options(
        selectinload(Order.items).selectinload(OrderItem.product)
    ).where(Order.id == id)

    order = db.session.execute(stmt).scalar_one_or_none()
    if not order:
        raise NotFound(message=f"Order with id {id} not found")

    return jsonify(OrderOut().dump(order)), 200

@orders_bp.post("")
def create_order():
    """Tạo đơn hàng mới gồm danh sách OrderItems liên kết tới nhiều Product (Bài tập 2, Slide 42)."""
    if not request.is_json:
        raise BadRequest(message="Request content-type must be application/json")

    try:
        data = OrderIn().load(request.json or {})
    except ValidationError as err:
        return jsonify({"code": "validation_error", "message": "Validation failed", "errors": err.messages}), 422

    order_number = data.get("order_number") or f"ORD-{uuid.uuid4().hex[:8].upper()}"
    order = Order(
        order_number=order_number,
        customer_email=data["customer_email"],
        status="pending"
    )
    db.session.add(order)

    for item_data in data["items"]:
        prod = db.session.get(Product, item_data["product_id"])
        if not prod or prod.archived:
            raise NotFound(message=f"Product with id {item_data['product_id']} not found or archived")

        unit_price = item_data.get("unit_price_cents")
        if unit_price is None:
            unit_price = prod.price_cents

        order_item = OrderItem(
            order=order,
            product=prod,
            quantity=item_data["quantity"],
            unit_price_cents=unit_price
        )
        db.session.add(order_item)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise Conflict(message=f"Order with order_number '{order_number}' already exists")

    # Reload với eager loading để trả về trọn vẹn thông tin
    loaded = db.session.execute(
        db.select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.product)
        ).where(Order.id == order.id)
    ).scalar_one()

    return jsonify(OrderOut().dump(loaded)), 201

