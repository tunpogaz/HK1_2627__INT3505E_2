## Bài 1
![test1_w2](/Week2/screenshots/test1_w2.png)
1. Kiểm tra lấy danh sách khi chưa có dữ liệu:
   - Kết quả: Trả về mã status 200 OK, phần body chứa danh sách mảng rỗng data: [] và tổng số lượng total: 0.
2. Kiểm tra thiếu header JSON:
   - Kết quả: Trả về mã lỗi 415 UNSUPPORTED MEDIA TYPE, kèm thêm thông báo {"error": "expected JSON"}.
3. Kiểm tra dữ liệu không đầy đủ (thiếu title/author):
   - Kết quả: Trả về mã lỗi 422 UNPROCESSABLE ENTITY, kèm thêm thông báo {"error": "title and author required"}.
4. Kiểm tra tạo sách mới thành công:
   - Kết quả:
     + Trả về mã status 201 CREATED.
     + Header chứa Location: /books/1 dẫn tới tài nguyên vừa sinh.
     + Body trả về đối tượng cuốn sách hoàn chỉnh kèm mã ID tự tăng (id: 1).
## Bài 2
![test2_1_w2](/Week2/screenshots/test2_1_w2.png)
![test2_2_w2](/Week2/screenshots/test2_2_w2.png)
1. Kiểm tra lấy chi tiết tài nguyên và Cache-Control:
    - Kết quả: Trả về 200 OK, dữ liệu chi tiết cuốn sách có id: 1và header Cache-Control: max-age = 60
2. Kiểm tra cập nhật một phần:
    - Kết quả: Trả về 200 OK, trường price được cập nhật thành 19.99, các thông tin còn lại (title, author, isbn) được giữ nguyên vẹn.
3. Kiểm tra thay thế toàn bộ tài nguyên (PUT):
    - Kết quả: Trả về 200 OK, dữ liệu được cập nhật lại theo payload mới; các trường không gửi lên (isbn, price) bị gán giá trị null.
4. Kiểm tra xoá tài nguyên thành công (DELETE):
    - Kết quả: Trả về mã 204 NO CONTENT với body hoàn toàn rỗng.
5. Kiểm tra xoá lại tài nguyên đã bị xoá:
    - Kết quả: Trả về mã lỗi 404 NOT FOUND cùng thông báo {"error": "not found"}
## Bài 3
![test3_1_w2](/Week2/screenshots/test3_1_w2.png)
![test3_2_w2](/Week2/screenshots/test3_2_w2.png)
![test3_3_w2](/Week2/screenshots/test3_3_w2.png)
1. Kiểm tra phân trang và sinh liên kết HATEOAS
    - Kết quả: Trả về mã status 200 OK, header Cache-Control: public, max-age=30, trả đúng 2 cuốn sách đầu tiên kèm liên kết HATEOAS (first, last, next, self) và đối tượng pagination với total_pages: 2.
2. Kiểm tra lọc theo tác giả không tồn tại (author=Orwell):
    - Kết quả: Trả về 200 OK, mảng data: [] rỗng, total: 0 và total_pages: 1.
3. Kiểm tra tìm kiếm tương đối theo từ khóa tiêu đề (q=clean):
    - Kết quả: Trả về 200 OK, lọc chính xác 2 cuốn sách có chứa từ khóa "clean" trong tiêu đề.
4. Kiểm tra danh sách mặc định có Header Accept JSON:
    - Kết quả: Trả về 200 OK, trả đủ toàn bộ danh sách 3 cuốn sách theo cấu hình mặc định size=20.
5. Kiểm tra validation kiểu dữ liệu phân trang (page=abc):
    - Kết quả: Bắt lỗi tham số không hợp lệ, trả về mã lỗi 400 BAD REQUEST kèm thông báo {"error": "page and size must be int"}.