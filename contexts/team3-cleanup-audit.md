# Team3: đối chiếu bản flags-cleanup với full_rounds

Ngày kiểm tra: 2026-11-19 (Asia/Bangkok). SSH pool144, alias team3,
xác nhận hostname `team3`. Chỉ đọc source, systemd và SQLite mode=ro.
Không sửa VM, không restart, không xóa dữ liệu hay in giá trị flag.

## Thư mục đang chạy

`meko-boutique.service` active, chạy `/usr/bin/python3 /opt/meko-boutique/app.py`,
WorkingDirectory `/opt/meko-boutique`. Thư mục
`/opt/meko-boutique.backup-20261119-flags-cleanup` là bản đối chiếu cũ; tương tự
`/opt/meko-crypto.backup-20261119-flags-cleanup` đối chiếu với `/opt/meko-crypto`.
Tên backup không có nghĩa là service chạy từ thư mục backup.

## Những gì bản đang chạy đã sửa

- Thêm `/opt/meko-boutique/models/flags.py`: nhận dạng flag và marker bằng regex.
  `flagged_row_ids():19` chọn mọi flag trừ bản mới; `prune_to_latest_flag():38`
  xóa hết các flag ngoài bản mới nhất. Không có metadata run/tick/expiry.
- `models/database.py`: gọi prune khi startup cho notes/orders/offers/backup,
  xóa marker và private outfit cũ khi startup.
- `models/catalog.py:18`, `models/shop.py:54,104,121` và các controller tương ứng:
  khi ghi flag mới, xóa các flag khác. Sau khi đọc marker thì xóa marker, riêng
  order chỉ xóa memo, giữ order. Cách này không dọn tài khoản và không dọn đầy đủ
  dữ liệu liên quan.
- `models/outfits.py:54,111`: giữ một private flag file, xóa file flag trước;
  thêm `current.json` làm alias và `read_preview():150` để traversal đọc flag hiện
  tại. Alias là thay đổi riêng của đường khai thác, không phải chính sách expiry.
- `/opt/meko-crypto/service.py:129,141`: tick mới hoặc record mới xóa toàn bộ flags;
  startup cũng chỉ giữ một record. Tick cũ bị từ chối bằng `stale_tick` mà không
  có run_id, nên một cuộc thi mới bắt đầu từ tick thấp có thể bị chặn.
- `models/shop.py:90` trên VM vẫn có LIMIT 100 trong query xuất backup.
- Không thấy timer riêng cho Meko cleanup trong `systemctl list-timers --all`;
  các thay đổi nêu trên dọn ngay trong request hoặc startup.

## Số liệu tại thời điểm đọc

| Dữ liệu | Số lượng |
| --- | ---: |
| customers | 2503 |
| orders | 4 (1 chứa flag) |
| order_items | 571, trong đó 563 không còn order tương ứng |
| outfits (database) | 622 |
| designs files | 623 |
| private files | 2 (1 flag + current.json alias) |
| collection_notes | 1 flag, 0 marker |
| vip_offers | 1 flag, 0 marker |
| reconciliation_notes | 1 flag, 0 marker |
| curveball / padding_oracle / ecdsa_nonce | mỗi service 1 flag tại tick 20 |

Không có bảng checker_groups/resources/receipts/windows trên VM: bản sửa hiện tại
của E:/full_rounds chưa được triển khai lên team3.

## Cần đưa gì vào source full_rounds

Giữ source đang sửa ở `E:/full_rounds` làm điểm làm việc. Bản sửa đó đã dọn check
bằng group nguồn gốc, dùng receipt cho PUT retry, xuất backup không LIMIT 100,
rollback upload và dọn DB/file/account theo metadata. Nối ForcAD theo tài liệu
`forcad-lifecycle-integration.md` trước khi bật prune flag.

Không chép nguyên `models/flags.py` hoặc các hàm giữ duy nhất flag mới nhất từ
team3 về source: `competition.verify()` của ForcAD đã đối chiếu vẫn đọc ba tick
`max(1,tick-2)..tick`. Chính sách giữ một flag có thể làm mất flag còn cần GET.
Không xóa các dữ liệu legacy chỉ dựa vào regex hoặc số lượng; cần đối chiếu riêng.

Nếu alias `current.json` là một phần thiết kế challenge cần giữ từ bản VM này,
port riêng phần cập nhật alias và `read_preview()` sau khi chốt hành vi; thay phần
xóa flag cũ bằng lifecycle. Bản E:/full_rounds hiện giữ đường traversal ban đầu,
chưa có alias ổn định được bổ sung riêng trên team3. Không tự đồng bộ cả thư mục
VM vì như vậy sẽ nhập lại chính sách giữ một flag và bỏ mất các sửa lifecycle.
