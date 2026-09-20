# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** Làm cá nhân
**Thành viên:** Bui Le Thai Son - 02880  
**Ngày:** 2026-09-19

## 1. Lựa chọn tài liệu

### Chủ đề & lý do chọn

**Chủ đề:** Chính sách Shopee về trả hàng, hoàn tiền, bảo hành và trách nhiệm người bán.

Nhóm chọn Shopee vì đây là nền tảng thương mại điện tử phổ biến, có các trang trợ giúp công khai và có đủ nội dung cho cả `buyer`, `seller`, và `both`. Bộ tài liệu tập trung vào các mốc thời gian, điều kiện xử lý và trách nhiệm của từng bên để benchmark retrieval có câu trả lời kiểm chứng được.

### Danh sách tài liệu

| # | Tên tài liệu | Nguồn | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|-------|----------------------|----------|-----------------|
| 1 | Shopee Đảm Bảo và quyền trả hàng hoàn tiền | https://help.shopee.vn/portal/4/article/79314 | 2026-09-19 / not-stated | ~1.100 | `audience=buyer`, `category=buyer-protection`, `language=vi`, `platform=shopee` |
| 2 | Quy trình Shopee xử lý yêu cầu trả hàng hoàn tiền | https://help.shopee.vn/portal/4/article/190242 | 2026-09-19 / not-stated | ~1.700 | `audience=buyer`, `category=return-refund-process`, `language=vi`, `platform=shopee` |
| 3 | Thời gian nhận lại voucher và tiền hoàn sau hủy đơn | https://help.shopee.vn/portal/4/article/79296 | 2026-09-19 / not-stated | ~1.400 | `audience=buyer`, `category=refund-timeline`, `language=vi`, `platform=shopee` |
| 4 | Chính sách bảo hành trên Shopee | https://help.shopee.vn/portal/4/article/77245 | 2026-09-19 / not-stated | ~1.600 | `audience=both`, `category=warranty`, `language=vi`, `platform=shopee` |
| 5 | Quy định người bán Shopee Mall về hoàn tiền và phí phát sinh | https://help.shopee.vn/portal/4/article/77262 | 2026-09-19 / not-stated | ~1.900 | `audience=seller`, `category=seller-settlement`, `language=vi`, `platform=shopee` |

**Data governance checklist:**
- [x] Corpus chỉ chứa nguồn công khai và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version`, `audience`, và trường lọc bổ sung.

### Cấu trúc metadata

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích? |
|----------------|------|---------------|------------------|
| `doc_id` | string | `shopee-dam-bao` | Truy vết tài liệu gốc và chấm gold answer |
| `source_url` | string | URL Shopee Help Center | Kiểm chứng nguồn |
| `retrieved_at` | date | `2026-09-19` | Biết thời điểm lấy dữ liệu |
| `document_version` | string | `not-stated` | Ghi phiên bản nếu nguồn nêu; không bịa |
| `audience` | enum | `buyer`, `seller`, `both` | Lọc theo đối tượng |
| `category` | string | `return-refund-process` | Lọc hoặc phân tích theo loại chính sách |
| `language` | string | `vi` | Quản lý corpus đa ngôn ngữ |
| `platform` | string | `shopee` | Hữu ích nếu mở rộng sang nhiều sàn |

## 2. Thiết kế chiến lược

### Phân tích đường cơ sở

Kết quả từ `python bench.py` trên 3 tài liệu mẫu:

| Tài liệu | Strategy | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|----------|----------|----------------|-------------------|--------------------------|
| `chinh-sach-bao-hanh-shopee.md` | FixedSize | 4 | 397.5 | Trung bình, có thể cắt ngang mục |
| `chinh-sach-bao-hanh-shopee.md` | Recursive | 4 | 358.5 | Khá tốt, ít cắt ngang ý |
| `chinh-sach-bao-hanh-shopee.md` | Heading | 6 | 238.3 | Dễ đọc, bám cấu trúc mục |
| `quy-dinh-nguoi-ban-shopee-mall.md` | FixedSize | 4 | 451.2 | Giữ nhiều ngữ cảnh nhưng hơi dài |
| `quy-dinh-nguoi-ban-shopee-mall.md` | Recursive | 5 | 329.4 | Cân bằng tốt |
| `quy-dinh-nguoi-ban-shopee-mall.md` | Heading | 6 | 274.2 | Truy vết tốt theo mục |
| `quy-trinh-tra-hang-hoan-tien.md` | FixedSize | 3 | 488.0 | Chunk dài, có thể lẫn nhiều ý |
| `quy-trinh-tra-hang-hoan-tien.md` | Recursive | 4 | 339.5 | Tốt nhất trong benchmark |
| `quy-trinh-tra-hang-hoan-tien.md` | Heading | 6 | 225.7 | Rõ mục, nhưng có thể tách câu hỏi khỏi mốc thời gian |

### Chiến lược của từng thành viên

Vì làm cá nhân, tôi tự chạy ba chiến lược để so sánh:

**Chiến lược 1 — FixedSizeChunker**
- Dùng `chunk_size=500`, `overlap=50`.
- Lý do: làm baseline đơn giản, có overlap để giảm mất ngữ cảnh ở ranh giới.

**Chiến lược 2 — RecursiveChunker**
- Dùng `chunk_size=500`.
- Lý do: ưu tiên cắt theo đoạn/mục lớn trước, sau đó mới xuống dòng/câu/từ. Kết quả benchmark tốt nhất vì giữ ngữ cảnh trả lời đủ dài mà không quá vụn.

**Chiến lược 3 — HeadingChunker**
- Tách theo heading Markdown, section dài thì fallback sang `RecursiveChunker`.
- Lý do: văn bản chính sách thường được biên soạn theo mục; mỗi heading là một đơn vị ngữ nghĩa dễ trích dẫn.

Code nằm trong `bench.py`, class `HeadingChunker`.

### So sánh giữa các chiến lược

| Thành viên/Chiến lược | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------------------|----------------------|-----------|----------|
| FixedSizeChunker | 9 | Có overlap, ít mất dữ liệu | Có thể cắt giữa câu/mục |
| RecursiveChunker | 10 | Cân bằng tốt giữa ngữ cảnh và độ dài | Ít gắn với cấu trúc heading |
| HeadingChunker | 9 | Dễ đọc, truy vết nguồn tốt | Có thể tách trạng thái và mốc thời gian sang hai chunk khác nhau |

**Chiến lược tốt nhất:** RecursiveChunker tốt nhất trong lần chạy này vì đạt 10/10 và giữ được đủ ngữ cảnh cho câu hỏi về thời hạn 6 ngày. HeadingChunker vẫn đáng dùng cho demo vì source traceability tốt, nhưng cần overlap hoặc nối heading lân cận để tránh thiếu thông tin.

## 3. Câu hỏi đánh giá & chất lượng truy xuất

### Câu hỏi đánh giá & câu trả lời chuẩn

| # | Query | Gold Answer | Chunk chứa thông tin |
|---|-------|-------------|----------------------|
| 1 | Người mua có bao nhiêu ngày để yêu cầu trả hàng hoàn tiền sau khi giao hàng thành công? | 15 ngày kể từ khi đơn hàng cập nhật giao hàng thành công. | `shopee-dam-bao`, mục Phạm vi bảo vệ / Sau khi bấm Đã nhận được hàng |
| 2 | Khi Shopee đang xem xét yêu cầu trả hàng hoàn tiền thì bao lâu có kết quả? | 3-5 ngày làm việc, không tính chủ nhật, ngày lễ và Tết. | `quy-trinh-tra-hang-hoan-tien`, mục Thời gian xem xét |
| 3 | Sau khi được chấp nhận trả hàng và hoàn tiền người mua phải gửi hàng trong bao lâu? | Trong vòng 6 ngày kể từ khi nhận thông báo gửi trả hàng. | `quy-trinh-tra-hang-hoan-tien`, mục Hai phương án xử lý |
| 4 | Điều kiện bảo hành cơ bản trên Shopee gồm những gì? | Còn thời hạn bảo hành, còn tem/phiếu bảo hành, lỗi kỹ thuật không do người mua. | `chinh-sach-bao-hanh-shopee`, mục Điều kiện bảo hành cơ bản |
| 5 | Hủy đơn do hết hàng hoặc không xác nhận đúng hạn thì bị phí bao nhiêu? | 196.360 VND cho mỗi đơn hàng bị hủy. | `quy-dinh-nguoi-ban-shopee-mall`, mục Phí phát sinh do lỗi của người bán |

Query #1 dùng `metadata_filter={"audience": "buyer"}`. Query #5 dùng `metadata_filter={"audience": "seller"}`.

### Tổng hợp chất lượng truy xuất

| # | Câu hỏi | Chiến lược tốt nhất | Có chunk liên quan trong top-3? | Ghi chú |
|---|---------|---------------------|----------------------------------|--------|
| 1 | Thời hạn yêu cầu trả hàng hoàn tiền | Fixed/Recursive/Heading | Có | Filter buyer giữ kết quả đúng đối tượng |
| 2 | Thời gian Shopee xem xét | Fixed/Recursive | Có | Heading top-1 đúng chủ đề nhưng thiếu mốc 3-5 ngày |
| 3 | Thời hạn gửi trả hàng | Recursive/Heading | Có | Fixed lấy chunk đúng ở top-2 nhưng top-1 lệch sang Shopee Đảm Bảo |
| 4 | Điều kiện bảo hành | Fixed/Recursive/Heading | Có | Cả ba đều tốt |
| 5 | Phí người bán Shopee Mall | Fixed/Recursive/Heading | Có | Filter seller loại bớt chunk buyer khỏi top-3 |

**Metadata filter có giúp ích không?**  
Có, rõ nhất ở query #5. Câu hỏi cố ý không nói rõ đối tượng là người bán hay người mua. Không filter, top-3 của HeadingChunker có cả chunk `buyer` từ `shopee-dam-bao` và chunk `both` từ tài liệu bảo hành; khi dùng `metadata_filter={"audience": "seller"}`, top-3 chỉ còn các chunk `seller` từ tài liệu Shopee Mall. Query #1 không thay đổi nhiều vì query đã chứa nhiều từ khóa buyer rõ ràng.

## 4. Thuyết trình & bài học nhóm

**Insights để trình bày:**
- RecursiveChunker đạt điểm cao nhất vì giữ ngữ cảnh tốt hơn heading trong câu hỏi có mốc thời gian nằm gần nhưng không cùng section.
- HeadingChunker giúp trích dẫn và kiểm tra thủ công dễ hơn, phù hợp văn bản chính sách, nhưng cần xử lý section ngắn/liền kề cẩn thận.
- Metadata filter có giá trị khi corpus có tài liệu buyer và seller dùng chung từ khóa như trả hàng, hoàn tiền, thanh toán.

**Bài học rút ra:**  
Cùng một corpus nhưng cách chunk làm thay đổi top-k khá rõ. Không nên chỉ kiểm tra `doc_id`; cần kiểm tra chunk có thật sự chứa câu trả lời hay không.

**Nếu làm lại:**  
Tôi sẽ thêm overlap theo heading hoặc ghép các section ngắn liền kề để tránh tách trạng thái xử lý khỏi mốc thời gian. Tôi cũng sẽ thử embedding ngữ nghĩa thật thay vì lexical hash embedder để đánh giá gần thực tế hơn.

## Tự Đánh Giá

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu | 10 / 10 |
| Thiết kế chiến lược | 14 / 15 |
| Chất lượng truy xuất | 9 / 10 |
| Thuyết trình |  / 5 |
| **Tổng phần nhóm** | ** / 40** |
