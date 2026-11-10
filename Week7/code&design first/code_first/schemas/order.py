from marshmallow import Schema, fields, validate

class OrderItemIn(Schema):
    """Input schema for an item within an order."""
    product_id = fields.Int(required=True)
    quantity = fields.Int(required=True, validate=validate.Range(min=1))

class OrderIn(Schema):
    """Input schema for creating a new Order with multiple OrderItems (Slide 42)."""
    order_number = fields.Str(required=True, validate=validate.Length(min=3, max=64))
    customer_email = fields.Email(required=True)
    items = fields.List(
        fields.Nested(OrderItemIn),
        required=True,
        validate=validate.Length(min=1, error="Order must contain at least one item")
    )

class OrderItemOut(Schema):
    """Output schema for an order item."""
    id = fields.Int(dump_only=True)
    order_id = fields.Int()
    product_id = fields.Int()
    product_name = fields.Str()
    product_sku = fields.Str()
    quantity = fields.Int()
    unit_price_cents = fields.Int()

class OrderOut(Schema):
    """Output schema for an order with eager-loaded items."""
    id = fields.Int(dump_only=True)
    order_number = fields.Str()
    customer_email = fields.Str()
    status = fields.Str()
    created_at = fields.DateTime(dump_only=True)
    items = fields.List(fields.Nested(OrderItemOut))

