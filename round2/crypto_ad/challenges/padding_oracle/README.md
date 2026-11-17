# Padding Oracle

- **Cổng:** TCP 9012.
- **Handler:** `challenge.py`.
- **Protocol:** JSON line; operations `info`, `targets`, `ciphertext`, `encrypt`, `decrypt`.
- **Mục tiêu:** xử lý tài liệu AES-CBC; bản vulnerable không xác thực MAC khi giải mã và trả hai mã lỗi opaque, ổn định theo record, cho lỗi padding và lỗi nội dung.
- **Bản vá:** khi `PATCHED=1`, kiểm tra HMAC trước khi giải mã và trả lỗi chung.
- **Triển khai:** `meko-crypto@padding_oracle.service`.

Người chơi cần tự hiệu chuẩn ý nghĩa hai mã lỗi bằng một tài liệu đã biết; không dựa vào chữ `padding`/`content` trong response. Giữ trạng thái vulnerable theo luật round. Hiệu chỉnh giới hạn tải để không cản lưu lượng checker/gameplay hợp lệ.
