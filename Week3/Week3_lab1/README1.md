# Lab 1: Thiết kế resource cho Blog API

## 1. Xác định resources trong miền
Các tài nguyên chính của nền tảng blog đơn giản bao gồm: bài viết, bình luận, thẻ, và hồ sơ người dùng. Hệ thống cũng có chức năng đăng ký theo dõi.

## 2. Phân loại Collection / Item / Sub-resource
- Collection: /users, /posts, /tags, /follow
- Item: /users/<id>, /posts/<id>, /tags/{slugs}, /comments/<id>
- Sub-resources: /users/{id}/profile, /users/{id}/followers, /users/{id}/following

## 3. Sơ đồ cây endpoint và version segment
- Users:
  - GET /api/v1/users: Danh sách người dùng
  - GET /api/v1/users/{id}: Chi tiết hồ sơ một người dùng
  - GET /api/v1/users/{id}/followers: Danh sách người theo dõi
  - POST /api/v1/users/{id}/followers: Thực hiện hành động theo dõi
- Posts, comments
  - GET /api/v1/posts: Danh sách bài viết
  - POST /api/v1/posts: Tạo bài viết mới
  - GET /api/v1/posts/{id}: Chi tiết bài viết
  - PUT /api/v1/posts/{id}: Cập nhật bài viết
  - DELETE /api/v1/posts/{id}: Xóa bài viết
  - GET /api/v1/posts/{id}/comments: Danh sách bình luận của bài viết đó
  - POST /api/v1/posts/{id}/comments: Thêm bình luận vào bài viết
- Tags:
  - GET /api/v1/tags: Danh sách toàn bộ các thẻ