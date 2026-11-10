from flask.views import MethodView
from flask_smorest import Blueprint
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from shared.extensions import db
from shared.models import Order, OrderItem, Product
from shared.errors import NotFound, BadRequest, Conflict
try:
    from code_first.schemas import OrderIn, OrderOut
except ImportError:
    from schemas import OrderIn, OrderOut

orders_blp = Blueprint(
    "orders",
    __name__,
    url_prefix="/api/v1/orders",
    description="Orders and OrderItems management with eager loading (Slide 20, 21, 42)"
)

@orders_blp.route("")
class OrderList(MethodView):
    """Resource handling Order listing (with eager loading) and creation (Slide 20, 21, 42)."""

    @orders_blp.response(200, OrderOut(many=True))
    def get(self):
        """Lấy danh sách tất cả các đơn hàng kèm OrderItems sử dụng selectinload để tránh lỗi N+1 query."""
        stmt = db.select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.product)
        ).order_by(Order.id)
        
        orders = db.session.execute(stmt).scalars().all()
        return orders

    @orders_blp.arguments(OrderIn)
    @orders_blp.response(201, OrderOut)
    def post(self, data):
        """Tạo đơn hàng mới cùng danh sách OrderItem liên kết với Product."""
        order_number = data["order_number"]
        customer_email = data["customer_email"]
        items_data = data["items"]

        order = Order(
            order_number=order_number,
            customer_email=customer_email,
            status="pending"
        )
        db.session.add(order)

        for item_data in items_data:
            product = db.session.get(Product, item_data["product_id"])
            if not product or product.archived:
                raise NotFound(message=f"Product with id {item_data['product_id']} not found or archived")

            order_item = OrderItem(
                order=order,
                product=product,
                quantity=item_data["quantity"],
                unit_price_cents=product.price_cents
            )
            db.session.add(order_item)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise Conflict(message=f"Order with order_number '{order_number}' already exists")

        # Reload with eager loading to return complete representation
        loaded_order = db.session.execute(
            db.select(Order).options(
                selectinload(Order.items).selectinload(OrderItem.product)
            ).where(Order.id == order.id)
        ).scalar_one()

        return loaded_order

@orders_blp.route("/<int:id>")
class OrderDetail(MethodView):
    """Resource handling single order details with eager loading (Slide 20, 21, 42)."""

    @orders_blp.response(200, OrderOut)
    def get(self, id):
        """Lấy thông tin chi tiết một đơn hàng cùng các OrderItem."""
        stmt = db.select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.product)
        ).where(Order.id == id)
        
        order = db.session.execute(stmt).scalar_one_or_none()
        if not order:
            raise NotFound(message=f"Order with id {id} not found")
        return order

