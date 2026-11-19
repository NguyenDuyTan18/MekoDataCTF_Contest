> LƯU Ý: Đây là phương án metadata nhiều tick trước khi ghép bản Desktop.
> Bản hiện tại giữ một flag/task giống team3. Xem README.md, mục Vòng đời dữ liệu checker.
> Không áp dụng nguyên hướng dẫn này cho chính sách một flag.

# Điểm nối ForcAD cho vòng đời checker

Source được đối chiếu (chỉ đọc):
`C:/Users/Admin/Desktop/MekoData_Ky/atk_def_platform/platform/ForcAD-demo`.
Các số dòng dưới đây thuộc checkout lúc kiểm tra ngày 2026-11-19.

## Các chỗ cần sửa bên source ForcAD

1. `backend/lib/storage/competition.py:59` — `ensure_schema()`:
   thêm `run_id` bền vững vào trạng thái cuộc thi. Cấp UUID một lần cho cuộc thi mới,
   giữ qua restart tiến trình, pause/resume và chuyển slot Web/Crypto. Lưu nó cùng
   `MekodataPlacements` hoặc metadata placement, trước khi gửi PUT lần đầu.
2. `competition.py:457` — `put_flag()` đã lưu seed vào `MekodataPlacements` và lấy
   lại seed khi retry. Tiếp tục dùng seed đó làm `key`; không dùng UUID của hộp thư
   RPC làm key. Truyền snapshot lifecycle vào `CheckerRunner(...).put()` ở dòng 476.
   Metadata của cùng placement phải giữ nguyên `run_id`, `tick`, `expires_tick`.
3. `competition.py:505` — `verify()` thực tế SELECT `round BETWEEN max(1,tick-2)
   AND tick`. Đây là cửa sổ ba tick, rộng hơn luật nhận flag tấn công trong
   `record_attack()` dòng 759. Với luồng hiện tại, placement tick `p` cần
   `expires_tick=p+3`, còn `oldest_live_tick=max(1,current_tick-2)` trong lúc thi.
   Không dùng `GameConfig.flag_lifetime=1` để quyết định xóa dữ liệu checker.
   Nếu thay đổi verify sau này, phải cập nhật hai mốc cùng chỗ.
4. `backend/lib/helpers/checkers.py:10` — `CheckerRunner`: nhận lifecycle và
   chuyển JSON sang subprocess bằng một biến môi trường riêng, ví dụ
   `MEKO_CHECKER_LIFECYCLE`. Kiểm tra `run_generic_command()` để truyền env theo
   từng subprocess; tránh sửa `os.environ` dùng chung vì PUT chạy nhiều thread.
5. `checkers/_shared/forcad_rpc.py:42` — `main()`: đọc biến môi trường đó, parse
   JSON và thêm `payload['lifecycle']`. `key` đã được lấy đúng từ `sys.argv[3]`
   ở dòng 52. Thêm đường gọi `prune` chuyên biệt, nhận task/ip và snapshot mà
   không đòi flag/locator. Không cần sửa các wrapper `full_rounds/*.py`.
6. `collect_checker.py:30` — `process_rpc()` đã chuyển nguyên `data['payload']`
   qua SSH ở dòng 47. Chỉ cần đảm bảo giữ nguyên lifecycle và chấp nhận action
   prune nếu sau này thêm allowlist. Không tính TTL ở collector.
7. `competition.py:562` — `pump()`: gửi prune cho từng đội/task ở ranh giới tick,
   sau khi PUT/GET cũ đã kết thúc và trước khi đặt tick mới. Đoạn `checking`
   hiện đã có `collect_puts(wait=True)` và đợi `pool.map(verify, ...)` hoàn tất.
   Snapshot phải lấy từ trạng thái thi thật; không lấy từ đồng hồ VM checker.
   Dùng job bảo trì riêng có retry, tránh biến lỗi prune thành điểm SLA sai.
8. `competition.py:817`, `:865`, `:913` — `archive_competition()`,
   `recreate_from_archive()`, `restart_competition()`: lưu công việc prune cuối
   của run cũ bền vững trước khi xóa placement/state. Chỉ gửi sau khi đóng cổng
   nhận flag và drain mọi job. Có thể dùng `current_tick` và `oldest_live_tick`
   bằng `max_expires_tick` của run cũ để dọn hết. Chỉ cấp run_id mới khi bắt đầu
   cuộc thi mới từ tick 0; không cấp mới khi chỉ khởi động lại tiến trình.

## Payload agent đã hỗ trợ ở E:/full_rounds

```json
{
  "task": "upload",
  "action": "put",
  "ip": "10.90.0.11",
  "key": "seed-da-luu-trong-MekodataPlacements",
  "flag": "FLAG",
  "lifecycle": {
    "run_id": "uuid-cua-luot-thi",
    "tick": 12,
    "expires_tick": 15,
    "current_tick": 12,
    "oldest_live_tick": 10
  }
}
```

Để dọn riêng, gửi `action: "prune"`, giữ `task`, `ip`, và lifecycle gồm
`run_id`, `current_tick`, `oldest_live_tick`. Gọi riêng từng task của mỗi đội;
Crypto cần cả curveball, padding_oracle và ecdsa_nonce. Các agent trả status 101
khi thành công. Khi không gửi lifecycle, dữ liệu flag được giữ lại.

## Đưa source sang pool

Source challenge đang sửa là `E:/full_rounds`. Bản cùng tên ở
`atk_def_platform/labs/full_rounds` chưa được cập nhật trong phiên này.
Đưa thay đổi của `app/`, `checker/`, `round2/crypto_ad/` sang repo/revision mà
CyberRangeCZ dùng, rồi cập nhật VM đội và VM checker cùng đợt. Migration schema
tự chạy khi dịch vụ khởi động. Giữ nguyên state, secret, token và patches hiện có.

554 ghi chú cũ không có metadata nguồn gốc không được tự xóa bằng tiền tố;
cần đối chiếu với dữ liệu thi hoặc xác nhận đây là database thử trước khi dọn.
