# api/products.py — function name trùng operationId (Slide 9)
from sqlalchemy.exc import IntegrityError
from models import db, Product

def list_products():
    """Lấy danh sách sản phẩm (Slide 9)."""
    rows = db.session.execute(
        db.select(Product).where(Product.archived.is_(False))
    ).scalars().all()
    return [p.to_dict() for p in rows], 200

def create_product(body):
    """Tạo sản phẩm mới (Slide 9)."""
    p = Product(**body)
    db.session.add(p)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"code": "conflict", "message": "SKU already exists"}, 409
    return p.to_dict(), 201

def get_product(id):
    """Lấy chi tiết 1 sản phẩm (Slide 9)."""
    p = db.session.get(Product, id)
    if not p or p.archived:
        return {"code": "not_found", "message": f"Product {id} not found"}, 404
    return p.to_dict(), 200

def patch_product(id, body):
    """Cập nhật sản phẩm."""
    p = db.session.get(Product, id)
    if not p or p.archived:
        return {"code": "not_found", "message": f"Product {id} not found"}, 404
    for k, v in body.items():
        if hasattr(p, k) and v is not None:
            setattr(p, k, v)
    db.session.commit()
    return p.to_dict(), 200

def delete_product(id):
    """Xóa mềm sản phẩm (Slide 24, 28)."""
    p = db.session.get(Product, id)
    if not p or p.archived:
        return {"code": "not_found", "message": f"Product {id} not found"}, 404
    p.archived = True
    db.session.commit()
    return "", 204

def reserve_product(id, body):
    """Đặt trước tồn kho (Slide 24, 28)."""
    p = db.session.get(Product, id)
    if not p or p.archived:
        return {"code": "not_found", "message": f"Product {id} not found"}, 404
    qty = body.get("qty", 1)
    if p.qty_in_stock < qty:
        return {"code": "out_of_stock", "message": f"Only {p.qty_in_stock} left"}, 409
    p.qty_in_stock -= qty
    db.session.commit()
    return p.to_dict(), 200
