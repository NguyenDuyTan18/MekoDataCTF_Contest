# Vòng 2 · Crypto AD

Ba dịch vụ nhận JSON qua TCP, mỗi yêu cầu trên một dòng. Mỗi challenge có handler và hướng dẫn riêng trong `challenges/<tên>/`; protocol P-256/JSON dùng chung nằm trong `protocol.py`, còn `service.py` là khung TCP, lưu flag và dispatcher.

| Challenge | Cổng | Chủ đề |
| --- | ---: | --- |
| Curveball | 9011 | Xác thực tham số đường cong P-256 |
| Padding Oracle | 9012 | Xử lý lỗi khi giải mã AES-CBC |
| ECDSA Nonce | 9013 | Sử dụng nonce khi ký ECDSA |

Mã và hướng dẫn theo bài:

- `challenges/curveball/challenge.py` · `challenges/curveball/README.md`
- `challenges/padding_oracle/challenge.py` · `challenges/padding_oracle/README.md`
- `challenges/ecdsa_nonce/challenge.py` · `challenges/ecdsa_nonce/README.md`

Trên VM đội, đọc `~/crypto-lab/host_port.txt` để chọn đối thủ. Ví dụ, từ `team1` kết nối Curveball của `team2`.

```bash
nc 10.90.0.12 9011
```

Gửi `{"op":"info"}` để xem các thao tác của dịch vụ và `{"op":"targets"}` để xem các bản ghi đã được đặt flag. Danh sách ban đầu trống khi dịch vụ mới khởi động. Chờ BTC mở vòng 2 và nộp flag qua scoreboard do BTC cung cấp.

Source trên VM nằm ở `/opt/meko-crypto/`. Sau khi vá trên VM đội mình, khởi động lại đúng dịch vụ. Ví dụ, `sudo systemctl restart meko-crypto@curveball.service`.

Khi sửa một challenge, cập nhật handler riêng trong `challenges/<tên>/challenge.py` và triển khai đúng unit của bài. `service.py`/`protocol.py` là phần dùng chung; thay đổi ở đó cần áp dụng cho toàn bộ các service.

Playbook mặc định cài cả ba challenge khi tạo VM mới. Với pool đã provision, có thể truyền `crypto_ad_deploy_services` để chỉ cập nhật và restart module được chọn. Ví dụ extra-vars của Ansible:

```yaml
crypto_ad_deploy_services:
  - curveball
```

Các tên hợp lệ là `curveball`, `padding_oracle`, `ecdsa_nonce`. Cách deploy chọn lọc giả định VM đã có đủ ba module từ lần provision đầu. Thay đổi `service.py` hoặc `protocol.py` là thay đổi phần dùng chung và sẽ restart cả ba service.
