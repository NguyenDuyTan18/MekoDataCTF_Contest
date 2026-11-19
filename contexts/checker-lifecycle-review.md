# Kết quả ghép source Desktop vào full_rounds — 2026-11-19

Nguồn tham chiếu: C:/Users/Admin/Desktop/team3-source-20261119/meko-boutique và
meko-crypto. Đích làm việc: E:/full_rounds. Không sửa hai bản Desktop hoặc các VM.

## Hành vi cuối cùng

- Web giữ một nhóm flag đã PUT/GET thành công cho mỗi task, giống chính sách của
  bản Desktop. Kích hoạt nhóm mới sẽ dọn nhóm trước cùng tài khoản, record và file.
- Retry cùng key dùng lại receipt/locator. Nhóm đã bị thay không được tạo lại.
- Check kết thúc (thành công hoặc lỗi) dọn tài khoản và toàn bộ tài nguyên thử.
- Client cũ được dọn marker sau khi app tạo phản hồi, giống bản Desktop.
- Outfit giữ current.json và đường traversal; patch tiếp tục chặn traversal.
  Lỗi upload/DB dọn phần ghi dở. Alias được khôi phục khi khởi động lại.
- Export không giới hạn 100 dòng.
- Crypto dùng source Desktop giữ một flag/service, từ chối tick cũ và không tạo
  record trùng khi retry. Thêm reset có token cho BTC bắt đầu cuộc thi mới.
- Provisioning cài app, service và hai agent; bỏ cây challenges/challenges bị lồng nhầm.

Giữ nguyên handler challenge Crypto và các điều kiện vá Web. Không nhập database,
token hay thư mục backup vào source. Thay đổi có sẵn trong provisioning/trainee-access.yml
của người dùng được giữ nguyên.

## Bằng chứng

py -3 -m unittest discover -s tests: **10 tests đạt**, 34.751 giây, OK.

Tests bao gồm: check/put/retry/get cả năm task với patch bật/tắt; PUT mới thay flag
cũ mà không tăng số record/file/tài khoản; dọn check lỗi; PUT mới lỗi vẫn giữ flag
đang hoạt động; client cũ dọn marker và giữ nội dung thường; current.json đọc flag
khi chưa vá và bị chặn khi vá; alias khôi phục sau restart; export đủ 151 dòng;
upload lỗi hết kho/DB không để file dở; Crypto giữ một target, từ chối tick cũ,
giữ flag sau restart, reset sai token bị từ chối, reset đúng token cho phép tick thấp;
bộ source Crypto được cài theo provisioning khởi động độc lập.

Diff được kiểm tra khoảng trắng với cr-at-eol; giữ kiểu newline ban đầu của file.
Chưa push, triển khai hoặc tạo pool mới.

## Điều kiện ForcAD

Chính sách một flag theo Desktop thay phương án metadata nhiều tick trước đây.
Không cần payload lifecycle để tự thay/dọn flag. Source ForcAD bên Desktop được
đọc lại vẫn có competition.py:511 GET ba tick max(1,tick-2)..tick. Cần đổi cửa sổ
GET đó sang tick hiện tại trước khi thi với chính sách này; nếu không, GET flag đã
thay sẽ CORRUPT. Source ForcAD riêng không được sửa trong nhiệm vụ này.

## Tự đánh giá theo agent-self-evaluation

| Tiêu chí | Điểm | Bằng chứng / phần còn cần làm |
| --- | --- | --- |
| Accuracy | 4/5 | Mười test đạt, hai chế độ patch; chưa chạy pool thật. |
| Completeness | 4/5 | Đã ghép Web/Crypto/checker/provisioning; cửa sổ GET ở source ForcAD riêng cần được đồng bộ khi vận hành. |
| Clarity | 4/5 | README nêu chính sách một flag và reset; audit cũ là tài liệu lịch sử. |
| Actionability | 4/5 | Source và lệnh reset sẵn; cần đưa revision lên repo tạo pool. |
| Conciseness | 4/5 | Chi tiết nằm trong báo cáo, trả lời chỉ nêu kết quả và điều kiện ForcAD. |

Trung bình 4.0/5. Ưu tiên tiếp theo: đồng bộ cửa sổ GET, tạo pool thử, chạy chu kỳ
thật. Người dùng có thể đối chiếu đánh giá này qua test và README.
