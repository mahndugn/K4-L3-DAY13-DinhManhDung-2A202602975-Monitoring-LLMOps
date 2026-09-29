# Prompt versioning cơ bản

Mục tiêu của phần này là biết một request đã dùng prompt nào và có thể rollback an toàn. Đây không phải bài tối ưu prompt hoặc A/B testing.

## Prompt contract

Trong project Langfuse cá nhân `day13-k4-l3a-<MSSV>`, tạo text prompt tên `day13-chat`. Prompt phải giữ ba biến:

```text
Feature={{feature}}
Docs={{docs}}
Question={{message}}
```

App lấy prompt theo hai biến môi trường:

```dotenv
LANGFUSE_PROMPT_NAME=day13-chat
LANGFUSE_PROMPT_LABEL=production
```

Nếu Langfuse không khả dụng, app dùng template local và trace metadata ghi `prompt_source=local` hoặc `local-fallback` thay vì giả vờ đã lấy được prompt managed.

## Tạo và vận hành prompt versions

Có thể thao tác bằng UI Langfuse hoặc dùng helper trong repo. Helper đọc credentials
từ `.env` nhưng không in key ra terminal:

```powershell
python scripts/manage_prompts.py inspect
python scripts/manage_prompts.py initialize
python scripts/manage_prompts.py promote-v2
python scripts/manage_prompts.py rollback-v1
```

`initialize` chỉ tạo prompt khi tên `day13-chat` chưa có trong project; nếu đã có
version, script dừng để tránh tạo trùng. Script khởi tạo v1 với `baseline` và
`production`, rồi v2 với `candidate`. Sau khi chạy cùng workload cho hai label,
`promote-v2` chuyển `production` sang v2; `rollback-v1` đưa `production` về v1.
Chạy `inspect` sau mỗi thao tác để kiểm tra label thực tế.

## Việc cần làm

1. Tạo version 1, gắn labels `baseline` và `production`.
2. Tạo version 2 với một thay đổi nhỏ về format hoặc độ dài câu trả lời, gắn label `candidate`.
3. Chạy cùng một input với `LANGFUSE_PROMPT_LABEL=baseline` và `candidate`.
4. Mở hai trace, kiểm tra `prompt_name`, `prompt_label`, `prompt_version` và prompt link.
5. Chuyển label `production` sang version 2, chạy lại một request.
6. Rollback `production` về version 1 và lưu ảnh evidence.

Không chấm prompt nào “hay hơn”. Điểm nằm ở khả năng truy xuất version, đổi label và rollback có bằng chứng.

## Evidence

- Một ảnh danh sách hai prompt version.
- Hai trace ID chứng minh hai version/label khác nhau.
- Một ảnh trước/sau khi đổi label hoặc rollback `production`.
- Ghi các ID và đường dẫn ảnh vào `submission/REPORT.md`.
