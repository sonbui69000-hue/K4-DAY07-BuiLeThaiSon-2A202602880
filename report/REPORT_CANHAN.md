# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Bui Le Thai Son - 02880
**Nhóm:** Làm cá nhân  
**Ngày:** 2026-09-19

## 1. Khởi động (Warm-up) — Cá nhân

### Độ tương tự Cosine

**Độ tương tự cosine cao nghĩa là gì?**  
Hai đoạn văn bản có cosine similarity cao thường nằm gần nhau trong không gian vector, tức là embedding xem chúng có nội dung hoặc ý nghĩa gần nhau. Điểm cao không nhất thiết là hai câu trùng từ, mà có thể là khác cách diễn đạt nhưng cùng ý.

**Ví dụ có độ tương tự cao:**
- Câu A: Người mua có thể yêu cầu trả hàng trong vòng 15 ngày.
- Câu B: Khách hàng được gửi yêu cầu hoàn tiền trong thời hạn mười lăm ngày.
- Tại sao tương đồng: hai câu đều nói về quyền yêu cầu trả hàng/hoàn tiền trong một mốc thời gian.

**Ví dụ có độ tương tự thấp:**
- Câu A: Sản phẩm còn tem bảo hành.
- Câu B: Trời mưa lớn ở Hà Nội.
- Tại sao khác: hai câu nói về hai chủ đề hoàn toàn khác nhau.

**Vì sao cosine similarity phù hợp hơn Euclidean distance cho text embeddings?**  
Cosine tập trung vào hướng của vector nên phù hợp để so sánh ý nghĩa, trong khi Euclidean distance dễ bị ảnh hưởng bởi độ lớn vector. Với text embedding đã chuẩn hóa, dot product và cosine similarity gần như tương đương.

### Bài toán Chunking

Tài liệu 10.000 ký tự, `chunk_size=500`, `overlap=50`:

```text
ceil((10000 - 50) / (500 - 50)) = ceil(9950 / 450) = 23 chunks
```

Kiểm tra bằng `FixedSizeChunker` cũng ra `23`.

Nếu tăng overlap lên 100:

```text
ceil((10000 - 100) / (500 - 100)) = ceil(9900 / 400) = 25 chunks
```

Overlap lớn hơn tạo nhiều chunk hơn, tốn lưu trữ và thời gian tìm kiếm hơn, nhưng giúp giữ ngữ cảnh ở ranh giới giữa hai chunk.

## 2. Hướng tiếp cận của tôi

### Các hàm chia nhỏ

**`SentenceChunker.chunk`**  
Tôi dùng regex tách tại vị trí sau dấu câu (`.`, `!`, `?`) để giữ lại dấu câu trong câu gốc. Sau đó gom tối đa `max_sentences_per_chunk` câu thành một chunk và loại bỏ khoảng trắng thừa. Edge case chưa xử lý hoàn hảo là chữ viết tắt và số thập phân có dấu chấm.

**`RecursiveChunker.chunk` / `_split`**  
Thuật toán thử separator từ lớn đến nhỏ: đoạn văn, dòng, câu, khoảng trắng, rồi cắt ký tự. Nếu một mảnh vẫn dài hơn `chunk_size`, hàm tiếp tục đệ quy với separator nhỏ hơn. Sau khi tách, các mảnh nhỏ được gom lại để tránh tạo quá nhiều chunk vụn.

### Lớp EmbeddingStore

**`add_documents` + `search`**  
Mỗi `Document` được biến thành một record gồm `id`, `content`, `metadata`, và `embedding`. Hàm `search()` embed query rồi tính dot product với từng record, sau đó sắp xếp giảm dần theo score.

**`search_with_filter` + `delete_document`**  
`search_with_filter()` lọc metadata trước rồi mới search để top-k không bị chiếm bởi tài liệu sai đối tượng. `delete_document()` xóa mọi chunk có `metadata["doc_id"]` khớp với doc_id cần xóa và trả về `True` nếu có record bị xóa.

### Tác tử KnowledgeBaseAgent

**`answer`**  
Agent lấy top-k chunk từ store, dựng prompt có đánh số nguồn `[1]`, `[2]`, `[3]`, rồi gọi `llm_fn`. Prompt yêu cầu chỉ dùng ngữ cảnh được cung cấp và nói rõ nếu không tìm thấy câu trả lời.

## 3. Hoàn thiện code

Kết quả kiểm thử:

```text
pytest tests/ -v
42 passed
```

**Số lượng bài test vượt qua:** 42 / 42

## 4. Dự đoán độ tương tự

Backend dùng cho bảng này là `_mock_embed`, nên điểm không phản ánh ngữ nghĩa thật; kết quả chủ yếu kiểm tra hàm cosine chạy đúng.

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Người mua có thể trả hàng trong 15 ngày | Khách hàng được yêu cầu hoàn tiền trong mười lăm ngày | cao | -0.0180 | Không |
| 2 | Người bán bị phí khi hủy đơn do hết hàng | Người bán không xác nhận đơn đúng hạn có thể bị tính phí | cao | 0.0173 | Không |
| 3 | Sản phẩm còn tem bảo hành | Trời mưa lớn ở Hà Nội | thấp | 0.0649 | Tạm đúng |
| 4 | Hoàn tiền về ví ShopeePay trong 24 giờ | Tiền hoàn có thể vào ví điện tử sau một ngày | cao | 0.1532 | Một phần |
| 5 | Bảo hành cần sản phẩm còn thời hạn | Thẻ tín dụng hoàn tiền trong 7 đến 14 ngày | thấp | 0.2180 | Không |

**Kết quả bất ngờ nhất:** cặp 5 có điểm cao nhất dù hai câu không cùng ý. Điều này xảy ra vì `_mock_embed` chỉ sinh vector giả lập từ hash, không mã hóa ngữ nghĩa; khi benchmark thật nên dùng embedding backend tốt hơn hoặc ít nhất ghi rõ hạn chế này.

## 5. Kết quả truy xuất của tôi

Tôi dùng corpus `data/chinh-sach-shopee/`, script `bench.py`, embedding `LexicalEmbedder` dependency-free, và chiến lược chính là chunk theo heading.

| # | Câu hỏi | Top-1 Chunk truy xuất được | Score | Relevant | Câu trả lời Agent-style |
|---|-------|-----------------------------|-------|----------|-------------------------|
| 1 | Người mua có bao nhiêu ngày để yêu cầu trả hàng hoàn tiền sau khi giao hàng thành công? | `shopee-dam-bao`, mục Phạm vi bảo vệ | 0.690 | Có | Người mua có thể yêu cầu trong 15 ngày. |
| 2 | Khi Shopee đang xem xét yêu cầu trả hàng hoàn tiền thì bao lâu có kết quả? | `quy-trinh-tra-hang-hoan-tien`, mục Nguyên tắc xử lý | 0.639 | Một phần | Chunk top-1 nói đúng trạng thái xem xét nhưng thiếu mốc 3-5 ngày. |
| 3 | Sau khi được chấp nhận trả hàng và hoàn tiền người mua phải gửi hàng trong bao lâu? | `quy-trinh-tra-hang-hoan-tien`, mục Hai phương án xử lý | 0.771 | Có | Người mua phải gửi hàng trong vòng 6 ngày. |
| 4 | Điều kiện bảo hành cơ bản trên Shopee gồm những gì? | `chinh-sach-bao-hanh-shopee`, mục Điều kiện bảo hành cơ bản | 0.599 | Có | Còn thời hạn bảo hành, còn tem/phiếu bảo hành, lỗi kỹ thuật không do người mua. |
| 5 | Hủy đơn do hết hàng hoặc không xác nhận đúng hạn thì bị phí bao nhiêu? | `quy-dinh-nguoi-ban-shopee-mall`, mục Phí phát sinh do lỗi của người bán | 0.543 | Có | Mức phí là 196.360 VND cho mỗi đơn hàng bị hủy. |

**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?** 5 / 5  
**Điểm theo script cho heading strategy:** 9 / 10

**Điều tôi học được:** chunk theo heading giúp chunk dễ đọc và truy vết nguồn tốt hơn, nhưng nếu một ý bị chia thành hai mục liên tiếp thì top-1 có thể đúng chủ đề mà thiếu mốc số liệu trả lời. Recursive chunking đạt điểm cao hơn trong lần chạy này vì giữ nhiều ngữ cảnh liền kề hơn.

## Tự Đánh Giá

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Khởi động | 5 / 5 |
| Hướng tiếp cận của tôi | 10 / 10 |
| Hoàn thiện code | 30 / 30 |
| Dự đoán độ tương tự | 4 / 5 |
| Kết quả truy xuất của tôi | 9 / 10 |
| **Tổng phần cá nhân** | **58 / 60** |
