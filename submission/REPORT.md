# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên: Đinh Mạnh Dũng**
- **MSSV: 2A202602975**
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/mahndugn/K4-L3-DAY13-DinhManhDung-2A202602975-Monitoring-LLMOps
- **Commit SHA cuối:** `c7fc24083740ef63a47fdf6f178c7877783cd93b`
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Langfuse project:** UI đang hiển thị tên `My Project` và được giữ nguyên theo lựa chọn của học viên. Evidence có prompt labels và trace cần thiết, nhưng tên hiển thị chưa khớp quy ước trong `docs/SUBMISSION.md` (`day13-k4-l3a-<MSSV>`).

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/19-pytest-final.txt` |
| Log validator | `evidence/17-cp3-log-validator.txt` |
| Dashboard validator | `evidence/18-cp3-dashboard-validator.txt` |
| Secret scan | `evidence/20-secret-scan.txt` |
| Structured log | `evidence/04-structured-log.txt` |
| PII redaction | `evidence/05-pii-redaction.txt` |
| Trace list | `evidence/06-trace-list.png`, `evidence/06-trace-list.txt` |
| Trace waterfall | `evidence/07-trace-waterfall.png`, `evidence/07-trace-waterfall.txt` |
| Trace metadata | `evidence/08-trace-metadata.png`, `evidence/08-trace-metadata.txt` |
| Prompt versions | `evidence/09-prompt-versions.png`, `evidence/09-prompt-versions.txt` |
| Prompt rollback | `evidence/10-prompt-rollback.txt` |
| Prompt rollback screenshot | `evidence/10-prompt-rollback.png` |
| Dashboard runtime snapshot | `evidence/11-dashboard-snapshot.txt` |
| Dashboard screenshot | `evidence/11-dashboard-overview.png` |
| Challenge workload | `evidence/12-cp3-load-run.txt` |
| Challenge metrics | `evidence/13-cp3-metrics.txt` |
| Challenge log/correlation | `evidence/14-cp3-log-correlation.txt` |
| Challenge trace waterfall | `evidence/15-cp3-trace-waterfall.txt` |
| Retrieval span comparison | `evidence/16-cp3-trace-retrieval-dominance.txt` |
| Challenge metrics screenshot | `evidence/12-cp3-metrics.png` |
| Challenge log screenshot | `evidence/13-cp3-log.png` |
| Challenge trace screenshot | `evidence/14-cp3-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | CP1 hoàn thiện correlation ID, metadata và scrub PII. |
| `validate_dashboard.py` | 6/6 | 6/6 | Contract có đủ sáu panel. |
| `pytest` | 22 passed | 22 passed | Toàn bộ public tests pass trên source CP2. |
| Số traces hợp lệ | Chưa thống kê | 72 có correlation ID | Langfuse trả 92 root traces trong 120 phút; 20 trace CP0 có ID `MISSING`, 72 trace còn lại nối được correlation ID. |
| Số PII leak | 0 | 0 | Log validator cuối quét 156 record. |
| Latency P95 / TTFT P95 | Chưa đo | 686.6 ms / 50 ms | Dashboard snapshot, rolling 60 phút tại thời điểm chụp. |
| Retrieval success rate | Chưa đo | 100% | Dashboard snapshot, rolling 60 phút tại thời điểm chụp. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware nhận `x-request-id` đúng định dạng `req-<8 hex>` hoặc sinh ID mới, bind vào structlog context và trả lại trong response header. Thời gian xử lý được trả trong `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** `user_id_hash`, `session_id`, `feature`, `model`, `env`, `correlation_id` và `trace_id`.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` đệ quy scrub các giá trị chuỗi trước `JsonlFileProcessor` và JSON renderer. Pattern che email, số điện thoại Việt Nam, CCCD và thẻ thanh toán.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100 trên 156 log record; 75 correlation ID duy nhất, 0 trường bắt buộc/enrichment thiếu và 0 PII leak. Xem `evidence/17-cp3-log-validator.txt` và `evidence/05-pii-redaction.txt`.

## 5. Tracing và prompt versioning

- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` có hai child: `knowledge-retrieval` (`RETRIEVER`) và `fake-llm-generate` (`GENERATION`). Generation ghi model, token usage, cost và prompt đã dùng.
- **Cách nối trace với log:** `correlation_id` có trong metadata trace và structured log; `trace_id` cũng được ghi vào `response_sent`.
- **Prompt name:** `day13-chat`.
- **Version/label baseline:** v1, labels `baseline` và `production` sau rollback.
- **Version/label candidate:** v2, label `candidate`.
- **Trace ID của mỗi version:** v1 baseline `71955fff7beff281a4f3a0e2f87a5c2b`; v2 candidate `8bf8357ed26257d7d854cc344ff23c58`; v2 production sau promote `dbfdbccc870eff1e8eafaa05b274c5b7`; v1 production sau rollback `67a08d70613c8cfa3eecbbd9505cff5f`.
- **Cách promote và rollback `production`:** `scripts/manage_prompts.py promote-v2` chuyển label sang v2; `rollback-v1` trả label về v1. Sau mỗi bước đã xác minh labels và tạo trace mới.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `scripts/dashboard.py` đọc `data/logs.jsonl` trong cửa sổ 60 phút và cập nhật mỗi 30 giây. Sáu panel hiển thị latency/TTFT, traffic, errors/retrieval success, cost, tokens và quality. Ảnh: `evidence/11-dashboard-overview.png`; số liệu: `evidence/11-dashboard-snapshot.txt`.
- **SLO và lý do chọn:** 99.5% request phải thành công trong 3000 ms theo rolling window 28 ngày; ngưỡng latency phù hợp với dashboard và baseline đo được.
- **Cách tính error budget:** 0.5% request trong cửa sổ được phép lỗi hoặc vượt 3000 ms, tương đương 5 request trên 1000 request đủ điều kiện.
- **Ba alert và runbook tương ứng:** Error rate trên 2% trong 5 phút (`alert-1`), request P95 trên 3000 ms trong 10 phút (`alert-2`), retrieval success dưới 90% trong 5 phút (`alert-3`); đều gửi Slack và có owner/runbook trong `config/alert_rules.yaml` và `docs/alerts.md`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (K4, incident `rag_slow`, feature `monitoring`).
- **Khoảng thời gian điều tra:** 2026-09-29 09:31:57–09:32:11 UTC (16:31:57–16:32:11 giờ Bangkok), 5 request.
- **Triệu chứng từ metrics:** P50 2,652 ms, P95/P99 3,170 ms, vượt ngưỡng challenge 2,000 ms và SLO latency 3,000 ms; TTFT P95 50 ms. Cả 5 request trả HTTP 200, error rate 0%, retrieval success 100%.
- **Log line và correlation ID liên quan:** `response_sent`, `req-07d3c97c`, latency 3,170 ms, trace `f0f856783139d9b0658c779db34b812f`. Bảng đủ 5 request nằm trong `evidence/14-cp3-log-correlation.txt`.
- **Trace ID và span gây ảnh hưởng:** Trace `f0f856783139d9b0658c779db34b812f`; root `lab-agent-run` 3,171 ms, `knowledge-retrieval` 2,501 ms, `fake-llm-generate` 152 ms. Retrieval chiếm khoảng 79% thời gian root; trace đối chiếu `95d407364bbc4351a59918041b0dfb00` cũng cho retrieval 2,501 ms.
- **Root cause:** Challenge bật `rag_slow`, khiến `retrieve()` trong `app/mock_rag.py` chờ 2,5 giây. Trace cho thấy phần lớn thời gian xử lý nằm ở retrieval. Ngoài ra, `main.chat` là hàm async nhưng gọi trực tiếp `agent.run` đồng bộ; ở concurrency 5, event loop bị chặn và các request phải xếp hàng. Vì vậy latency từ phía load test là 11,56–14,22 giây, còn `/metrics` và trace đo 2,65–3,17 giây sau khi handler bắt đầu. Trace được tạo khi label `production` của Langfuse trỏ tới v2; sau khi lưu evidence, label đã rollback về v1. Lượt chạy 5 request đầu cũng còn trong Langfuse; việc reload server lúc phát triển đã reset bộ đếm trong bộ nhớ nên workload được chạy lại và lượt thứ hai được ghi vào evidence CP3.
- **Fix action:** Tắt incident sau khi thu thập evidence; hiện cả ba cờ incident đều tắt. Với vector store thật, cần kiểm tra index và độ trễ mạng, đặt timeout, cân nhắc cache hoặc fallback. Chuyển xử lý đồng bộ sang worker pool hoặc triển khai I/O async để không chặn event loop.
- **Preventive measure:** Theo dõi retrieval P95 và cảnh báo tại ngưỡng challenge 2.000 ms. Đo thời gian toàn trình từ middleware để tính cả thời gian xếp hàng; duy trì cảnh báo request P95, trace retrieval có correlation ID và kiểm tra concurrency trước khi phát hành.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Tạo hoặc xác thực `correlation_id` ngay tại middleware, rồi truyền qua log và metadata trace. Nhờ một ID chung, có thể tìm đúng log và trace của request khi metric báo bất thường; `user_id_hash` và bước scrub giữ dữ liệu nhận dạng thô ra khỏi log.
- **Một lỗi/blocker đã gặp:** Log ban đầu dùng ID `MISSING`, thiếu request metadata; prompt `day13-chat` production chưa tồn tại trong Langfuse.
- **Cách tìm nguyên nhân và xử lý:** Log validator chỉ ra thiếu correlation/enrichment; middleware/context processor đã được hoàn thiện. Langfuse API trả 404 cho prompt; tạo v1/v2, gắn labels, sau đó xác minh trace và rollback.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metric khoanh vùng thời điểm và mức độ bất thường: trong challenge, P95 đạt 3.170 ms. Log của request `req-07d3c97c` cho latency 3.170 ms và trace ID `f0f856783139d9b0658c779db34b812f`. Mở trace đó thấy retrieval mất 2.501 ms trên tổng 3.171 ms, từ đó xác định thành phần gây chậm.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Version và label giúp biết prompt nào đang phục vụ production, thử candidate và quay lại baseline khi cần. Token/cost cho biết mức tiêu thụ, còn SLO/error budget cho biết lúc nào hiệu năng hoặc độ tin cậy không đạt mục tiêu. Rollback v2 về v1 đã được ghi bằng label và trace tương ứng.
- **Điều quan trọng nhất đã học:** Một request trả HTTP 200 vẫn có thể vi phạm mục tiêu latency. Cần đối chiếu metric, log và trace bằng cùng ID; đồng thời phân biệt thời gian xử lý trong handler với thời gian toàn trình mà client cảm nhận khi các request xếp hàng.
- **Hạn chế còn lại:** Ảnh Langfuse hiển thị `My Project`, chưa đúng quy ước tên project trong `docs/SUBMISSION.md`. Đường xử lý đồng bộ trong endpoint async và phép đo latency chưa bao gồm đầy đủ thời gian chờ hàng; các cải tiến này được nêu ở fix action nhưng chưa triển khai trong lab.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence được đưa vào cùng commit nộp bài.
- [x] Tất cả ảnh/output được dẫn bằng đường dẫn tương đối; các file được dẫn đều có trong `submission/evidence/`.
- [x] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence hiển thị tên project theo quy ước cá nhân trong `docs/SUBMISSION.md`; project hiện hiển thị `My Project` theo lựa chọn giữ nguyên tên. Ảnh đã kiểm tra không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
