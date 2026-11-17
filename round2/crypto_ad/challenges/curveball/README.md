# Curveball

- **Cổng:** TCP 9011.
- **Handler:** `challenge.py`.
- **Protocol:** JSON line; operations `info`, `targets`, `ca`, `sample`, `read`.
- **Mục tiêu:** kiểm tra chứng chỉ P-256; bài vulnerable cho phép client chọn generator khi xác minh chữ ký.
- **Bản vá:** khi `PATCHED=1`, chỉ chấp nhận generator chuẩn `G`.
- **Triển khai:** `meko-crypto@curveball.service`.

Giữ trạng thái vulnerable theo luật round. Chỉ bật bản vá trên VM đội cần thực hiện phòng thủ.
