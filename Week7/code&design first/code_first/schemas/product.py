from marshmallow import Schema, fields, validate, validates, ValidationError

class ProductOut(Schema):
    """Output serialization schema (Slide 26)."""
    id = fields.Int(dump_only=True)
    sku = fields.Str()
    name = fields.Str()
    description = fields.Str(allow_none=True)
    price_cents = fields.Int()
    qty_in_stock = fields.Int()
    archived = fields.Bool()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class ProductPaginationOut(Schema):
    """Paginated product list response schema (Slide 24, 27)."""
    items = fields.List(fields.Nested(ProductOut))
    page = fields.Int()
    size = fields.Int()
    total = fields.Int()

class ProductIn(Schema):
    """Input validation schema for product creation (Slide 26, 32)."""
    sku = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=32),
            validate.Regexp(r"^[A-Za-z0-9-]+$", error="SKU must be alphanumeric and hyphens only")
        ]
    )
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255)
    )
    description = fields.Str(allow_none=True, load_default=None)
    price_cents = fields.Int(
        required=True,
        validate=validate.Range(min=0, max=10_000_000)
    )
    qty_in_stock = fields.Int(
        load_default=0,
        validate=validate.Range(min=0)
    )

    @validates("name")
    def validate_name(self, value, **kwargs):
        if not value or value.strip() == "":
            raise ValidationError("Product name cannot be empty or blank")

class ProductPatch(Schema):
    """Partial update schema for product (Slide 26)."""
    name = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    price_cents = fields.Int(validate=validate.Range(min=0, max=10_000_000))
    qty_in_stock = fields.Int(validate=validate.Range(min=0))

class ReserveIn(Schema):
    """Schema for reserving product stock (Slide 26)."""
    qty = fields.Int(
        required=True,
        validate=validate.Range(min=1, error="Quantity must be at least 1")
    )

class ProductQueryArgs(Schema):
    """Query parameters for pagination (Slide 24, 27)."""
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    size = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))

