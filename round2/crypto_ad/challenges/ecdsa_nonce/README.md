# ECDSA Nonce

- **Cổng:** TCP 9013.
- **Handler:** `challenge.py`.
- **Protocol:** JSON line; operations `info`, `targets`, `pubkey`, `sign`, `unlock`.
- **Mục tiêu:** ký thông điệp bằng ECDSA P-256; bản vulnerable tái sử dụng nonce trong một ngữ cảnh thông điệp, khi hai thông điệp chỉ khác hậu tố ba ký tự.
- **Bản vá:** khi `PATCHED=1`, dùng RFC 6979 trên toàn bộ thông điệp để mỗi digest có nonce tương ứng.
- **Triển khai:** `meko-crypto@ecdsa_nonce.service`.

Checker vẫn xác minh hai chữ ký trên cùng request-id stem với hậu tố `one`/`two`; đừng đổi dạng probe này nếu muốn giữ checker tương thích. Giữ trạng thái vulnerable theo luật round. Chỉ bật bản vá trên VM đội cần thực hiện phòng thủ.
