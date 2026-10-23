from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import mapped_column, relationship
import bcrypt

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    username = mapped_column(String(50), unique=True, nullable=False)
    email = mapped_column(String(120), unique=True, nullable=False)
    password_hash = mapped_column(String(255), nullable=False)
    roles = mapped_column(String(100), default="user", nullable=False)     # ví dụ: "user" hoặc "admin,manager"
    scopes = mapped_column(String(255), default="posts:read,posts:write,profile", nullable=False)
    is_active = mapped_column(Boolean, default=True, nullable=False)
    created_at = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")

    def set_password(self, password: str):
        """Băm mật khẩu bằng bcrypt với salt ngẫu nhiên và cost=12 (Slide 27)."""
        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Xác minh mật khẩu an toàn với hàm so sánh hằng số thời gian chống timing attack."""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def get_roles_list(self):
        return [r.strip() for r in self.roles.split(",") if r.strip()]

    def get_scopes_list(self):
        return [s.strip() for s in self.scopes.split(",") if s.strip()]

    def to_public_dto(self):
        """
        Data Transfer Object công khai
        TUYỆT ĐỐI KHÔNG để lộ password_hash hoặc internal fields ra API response!
        """
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "roles": self.get_roles_list(),
            "scopes": self.get_scopes_list()
        }


class Post(db.Model):
    __tablename__ = "posts"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    title = mapped_column(String(200), nullable=False)
    content = mapped_column(Text, nullable=False)
    visibility = mapped_column(String(20), default="public", nullable=False)  # public, friends_only, private
    tags = mapped_column(String(150), default="general", nullable=False)
    created_at = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    author_id = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    author = relationship("User", back_populates="posts")

    def to_dto(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "visibility": self.visibility,
            "author": {
                "id": self.author.id if self.author else self.author_id,
                "username": self.author.username if self.author else "unknown"
            },
            "tags": [t.strip() for t in self.tags.split(",") if t.strip()],
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        }


class Friendship(db.Model):
    __tablename__ = "friendships"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    friend_id = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

