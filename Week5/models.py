"""
Week 5: Models for Bookstore API
- Book (id, title, isbn, price_vnd, stock, genre/category_id, created_at)
- Category / Genre (id, name, slug)
- Author (id, name, bio)
- BookAuthor (junction table với metadata role)
- Review (rating, comment, book_id, user_id)
- User (email, display_name)
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

db = SQLAlchemy()


class Category(db.Model):
    __tablename__ = "categories"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(100), nullable=False)
    slug = mapped_column(String(100), unique=True, nullable=False)

    books = relationship("Book", back_populates="category", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug
        }


class Author(db.Model):
    __tablename__ = "authors"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(100), nullable=False)
    bio = mapped_column(Text, nullable=True)

    books = relationship("Book", secondary="book_authors", back_populates="authors")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "bio": self.bio
        }


class BookAuthor(db.Model):
    __tablename__ = "book_authors"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    author_id = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"), nullable=False)
    role = mapped_column(String(50), default="lead")  # lead, co, editor


class Book(db.Model):
    __tablename__ = "books"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    title = mapped_column(String(200), nullable=False)
    isbn = mapped_column(String(13), unique=True, nullable=False)
    price_vnd = mapped_column(Integer, nullable=False)
    stock = mapped_column(Integer, default=0, nullable=False)
    created_at = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    category_id = mapped_column(ForeignKey("categories.id"), nullable=False)
    category = relationship("Category", back_populates="books")
    authors = relationship("Author", secondary="book_authors", back_populates="books")
    reviews = relationship("Review", back_populates="book", cascade="all, delete-orphan")

    def to_dict(self, fields=None):
        """
        Chuyển đổi sang API Resource representation:
        - Không để lộ raw DB column
        - Định dạng ISO 8601 cho thời gian
        - Nhúng thông tin category và authors
        - Hỗ trợ Field Selection nếu có truyền fields
        """
        full = {
            "id": f"book_{self.id}",
            "raw_id": self.id,
            "title": self.title,
            "isbn": self.isbn,
            "genre": self.category.slug if self.category else None,
            "category": self.category.to_dict() if self.category else None,
            "authors": [a.to_dict() for a in self.authors],
            "price": {
                "amount": self.price_vnd,
                "currency": "VND"
            },
            "stock": self.stock,
            "inStock": self.stock > 0,
            "createdAt": self.created_at.isoformat() if self.created_at else None
        }

        if fields is None:
            return full

        return {k: v for k, v in full.items() if k in fields}


class User(db.Model):
    __tablename__ = "users"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    email = mapped_column(String(120), unique=True, nullable=False)
    display_name = mapped_column(String(100), nullable=False)
    created_at = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    reviews = relationship("Review", back_populates="user")


class Review(db.Model):
    __tablename__ = "reviews"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    rating = mapped_column(Integer, nullable=False)  # 1 - 5 sao
    comment = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    book_id = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    user_id = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    book = relationship("Book", back_populates="reviews")
    user = relationship("User", back_populates="reviews")
