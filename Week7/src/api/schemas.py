from marshmallow import Schema, fields, validate, validates, ValidationError

# ─── Product Schemas (Slide 26, 32) ───

class ProductOut(Schema):
    """Output serialization schema cho Product (Slide 26)."""
    id = fields.Int(dump_only=True)
    sku = fields.Str()
    name = fields.Str()
    description = fields.Str(allow_none=True)
    price_cents = fields.Int()
    qty_in_stock = fields.Int()
    archived = fields.Bool()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class ProductIn(Schema):
    """Input validation schema tạo mới sản phẩm (Slide 26, 32)."""
    sku = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=32),
            validate.Regexp(r"^[A-Za-z0-9-]+$", error="SKU chỉ được chứa chữ cái, số và dấu gạch ngang")
        ]
    )
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255)
    )
    description = fields.Str(allow_none=True, load_default=None)
    price_cents = fields.Int(
        required=True,
        validate=validate.Range(min=0, max=10_000_000, error="Giá không được nhỏ hơn 0")
    )
    qty_in_stock = fields.Int(
        load_default=0,
        validate=validate.Range(min=0, error="Số lượng tồn kho không được âm")
    )

    @validates("name")
    def validate_name(self, value, **kwargs):
        if not value or value.strip() == "":
            raise ValidationError("Tên sản phẩm không được để trống")

class ProductPatch(Schema):
    """Schema cập nhật một phần thuộc tính (Slide 26)."""
    name = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    price_cents = fields.Int(validate=validate.Range(min=0, max=10_000_000))
    qty_in_stock = fields.Int(validate=validate.Range(min=0))

class ReserveIn(Schema):
    """Schema đặt trước hàng tồn kho (Slide 26)."""
    qty = fields.Int(
        required=True,
        validate=validate.Range(min=1, error="Số lượng đặt trước phải tối thiểu là 1")
    )

# ─── Order & OrderItem Schemas (Bài tập 2, Slide 42) ───

class OrderItemIn(Schema):
    product_id = fields.Int(required=True)
    quantity = fields.Int(required=True, validate=validate.Range(min=1))
    unit_price_cents = fields.Int(allow_none=True, load_default=None)

class OrderIn(Schema):
    order_number = fields.Str(load_default=None, validate=validate.Length(min=3, max=64))
    customer_email = fields.Email(required=True)
    items = fields.List(
        fields.Nested(OrderItemIn),
        required=True,
        validate=validate.Length(min=1, error="Đơn hàng phải chứa ít nhất 1 mặt hàng")
    )

class OrderItemOut(Schema):
    id = fields.Int(dump_only=True)
    order_id = fields.Int()
    product_id = fields.Int()
    product_name = fields.Str()
    product_sku = fields.Str()
    quantity = fields.Int()
    unit_price_cents = fields.Int()

class OrderOut(Schema):
    id = fields.Int(dump_only=True)
    order_number = fields.Str()
    customer_email = fields.Str()
    status = fields.Str()
    created_at = fields.DateTime(dump_only=True)
    items = fields.List(fields.Nested(OrderItemOut))

