# SPEC FINAL — AI Product Hackathon

**Nhóm:** _15_
**Thành viên**:
Nguyễn Công Nhật Tân - 2A202600141
Trần Nhật Minh - 2A202600300
Phan Nguyễn Việt Nhân - 2A202600279
Phan Anh Ly Ly - 2A202600421
Đồng Mạnh Hùng - 2A202600465

**Track:** ☐ VinFast · ☐ Vinmec · ☑ **VinUni-VinSchool** · ☐ XanhSM · ☐ Open
**Topic** : VinUni AI Academic Regulation Chatbot
**Problem statement (1 câu):** Sinh viên thường bối rối và mất thời gian chờ đợi phản hồi từ Phòng Đào tạo (PĐT) khi tra cứu quy chế học vụ, điều kiện tiên quyết, thủ tục hành chính bị phân mảnh; AI giúp tập hợp dữ liệu nội bộ và giải đáp tức thì, chính xác 24/7 thông qua một ứng dụng Web trực quan.

---

## 1. AI Product Canvas - Trần Nhật Minh - 2A202600300

|   | Value | Trust | Feasibility |
|---|-------|-------|-------------|
| **Câu hỏi** | User nào? Pain gì? AI giải gì? | Khi AI sai thì sao? User sửa bằng cách nào? | Cost/latency bao nhiêu? Risk chính? |
| **Trả lời** | *Sinh viên: Không biết tìm luật/quy chế ở đâu. PĐT: Quá tải email. AI gom data hệ thống thành Chatbot hỏi đáp 24/7 với Admin Portal cho PĐT.* | *AI trả lời kèm TRÍCH DẪN LINK GỐC. Nếu sai, sinh viên gửi feedback. Cán bộ PĐT có quyền Admin tự đăng nhập để xóa/đăng tải PDF quy chế mới ngay lập tức.* | *Cost: ~$0.005/query (RAG + GPT-4o-mini). Latency < 3s. Risk: Hallucinate sai điều kiện tốt nghiệp/học phí.* |

**Automation hay augmentation?** ☐ Automation · ☑ **Augmentation**
Justify: *Augmentation — Trợ lý AI cung cấp thông tin "tăng cường" khả năng tự quyết định của sinh viên. Phân hệ Admin giúp PĐT "tăng cường" tiến độ thông báo quy chế mới bằng UI hệ thống đăng tải thay vì sửa code trực tiếp.*

**Learning signal:**
1. User correction đi vào đâu? *Vào database logs để PĐT theo dõi tần suất câu hỏi sai/thiếu. PĐT lập tức Login vào trang quản trị tải lên file PDF đính chính.*
2. Product thu signal gì để biết tốt lên hay tệ đi? *Chất lượng bộ từ khoá bị chặn (Offensive, Mental Health, Financial); Tỷ lệ giải quyết triệt để vấn đề bằng tài liệu trích xuất từ ChromaDB.*
3. Data thuộc loại nào? ☐ User-specific · ☑ **Domain-specific** · ☐ Real-time · ☐ Human-judgment

---

## 2. User Stories — 5 paths - Phan Nguyễn Việt Nhân- 2A202600279

### Feature: *AI Academic Advisor (Hỏi đáp quy chế & lộ trình)*

**Trigger:** *Sinh viên mở Web Chat, gõ câu hỏi vào khung text.*

| Path | Câu hỏi thiết kế | Mô tả |
|------|-------------------|-------|
| Happy — AI chuẩn xác | User thấy gì? Flow kết thúc ra sao? | *Bot sinh câu trả lời mượt mà, ghi rõ đoạn trích dẫn gốc (VD: Trang 42 - PDF). Dữ liệu chat được lưu vào bộ nhớ cục bộ, sinh viên đọc xong tab.* |
| Low-confidence | System báo "không chắc" bằng cách nào? | *Quá trình xử lý Phân loại Ý định chốt là [Academic] nhưng RAG tìm không ra tài liệu, bot từ chối trả lời lụi.* |
| Failure — DB cũ | Recover ra sao? | *Bot lấy tài liệu năm cũ. Sinh viên đối chiếu cố vấn học tập thấy sai.* |
| Correction / Update — Admin | User sửa bằng cách nào? | *Trang `/management` dành cho Admin. PĐT login tài khoản (bảo mật qua `.env`), bấm Xóa tài liệu PDF cũ và Bấm Upload file mới lên hệ thống, tự động Sync vào VectorDB (ChromaDB).* |
| Guardrail — An toàn | Rủi ro nhạy cảm | *Sinh viên chat thô tục, hỏi rò rỉ học phí hoặc tìm cách tiêu cực. Bot rẽ nhánh ngay từ Bước 0 (Keyword check), không văng lên LLM, khóa cảnh báo lịch sử chuyển tiếp.* |

---

## 3. Eval metrics + threshold - Phan Anh Ly Ly - 2A202600421

**Optimize precision hay recall?** ☑ **Precision** · ☐ Recall
Tại sao? *Sự chính xác (Precision) là tối thượng. Bot thà không biết và đề nghị gặp PĐT thay vì tự quy đổi sai ra con số điều kiện ra trường khiến sinh viên mất tiền/thời gian.*

| Metric | Threshold | Red flag (dừng khi) |
|--------|-----------|---------------------|
| *Resolution Rate (Tự giải quyết tự động)* | *≥ 60%* | *< 40% trong 2 tuần liên tiếp* |
| *Retrieval Accuracy (Trích xuất đúng document)* | *≥ 95%* | *< 85% (Hệ thống tìm kiếm lỗi)* |
| *Hallucination Rate (Tự sinh/bịa số liệu)* | *< 2%* | *> 5% (Tạm đóng phần hỏi đáp tự do để fix prompt)* |

---

## 4. Top 4 failure modes - Đồng Mạnh Hùng - 2A202600465

| # | Trigger | Hậu quả | Mitigation |
|---|---------|---------|------------|
| 1 | *Hỏi về chính sách học bổng / học phí / tiền.* | *AI tự bịa con số gây nhầm lẫn ngân sách sinh viên.* | *Rule-based Guardrail: Chặn từ khoá (FINANCIAL). Trả ngay link liên hệ PĐT mà không qua AI.* |
| 2 | *Hỏi tiêu cực, tuyệt vọng, trầm cảm.* | *AI tư vấn vô cảm nguy hiểm.* | *Rule-based Guardrail (MENTAL_HEALTH): Chặn và hướng dẫn sang tay ngay bộ phận CS Tâm lý.* |
| 3 | *Dùng ngôn từ xúc phạm (Offensive).* | *Phản cảm, làm sai lệch Database log.* | *Rule-based Guardrail (OFFENSIVE): Chặn và nhắc nhở ngôn từ lịch sự trước bước gọi LLM.* |
| 4 | *PĐT ban hành quy định mới nhưng VectorDB chưa update.* | *AI trả lời bằng luật cũ khiến sinh viên lỡ nộp đơn.* | *Admin Management UI để PĐT có thể Upload/Delete file trực tiếp tự động Refresh Data.* |

---

## 5. ROI 3 kịch bản - Nguyễn Công Nhật Tân - 2A202600141

|   | Conservative | Realistic | Optimistic |
|---|-------------|-----------|------------|
| **Assumption** | *100 truy vấn/ngày, 50% tự giải quyết* | *300 truy vấn/ngày, 70% tự giải quyết* | *800 truy vấn/ngày (thời điểm đăng ký học), 85% tự giải quyết* |
| **Cost** | *$2/ngày* | *$5/ngày* | *$15/ngày* |
| **Benefit** | *Tiết kiệm 2h xử lý Email cho PĐT* | *Tiết kiệm 8h/ngày (tương đương biên chế 1 người)* | *Tiết kiệm 20h/ngày, vận hành xuyên trưa đêm* |

---

## 6. Mini AI spec (1 trang) - Cả team

**Sản phẩm:** VinUni AI Academic Regulation Chatbot (bản Web Flask)
**Dành cho:** Sinh viên (đặc biệt là tân sinh viên) và Cán bộ Phòng Đào tạo (PĐT).

**Product Giải Quyết Gì?**
Đóng vai trò "nhân viên PĐT ảo" cung cấp Web App trực tiếp giải đáp mọi thắc mắc học vụ. Tiết kiệm khối thời gian chờ đội phản hồi email, giải quyết nhanh các quy chế bằng RAG Agent, có bộ lưu trữ lịch sử chat.

**AI Làm Gì? (Augmentation)**
Hệ thống kiến trúc đa lớp:
- **Ngắn mạch rủi ro (Fast Guardrails):** Hệ thống chặn dòng chữ thô tục, câu hỏi học phí, hay trầm cảm tự tử một tĩnh tức khắc (Bypass không tốn Token API).
- **RAG Classifier:** Phân biệt ý định người dùng (Hỏi xã giao, Hỏi linh tinh, hay Hỏi quy chế).
- **Truy Xuất (Retrieval):** Dùng text-embedding-3-small nhúng câu hỏi vector lên cở sở đồ thị ChromaDB để tìm chính xác quy định.
- **Quản lý dữ liệu Admin:** Module giao diện độc quyền cho Cán bộ dễ dàng xóa hay cập nhật PDF quy định mới.

**Chất Lượng (Optimize for Precision)**
Nguyên tắc: "Độ tin cậy được thể hiện qua TRÍCH DẪN RÕ RÀNG". Mọi câu trả lời bắt buộc gắn nhãn tham chiếu xuất xứ. Mức an toàn được đặt lên mức tối đa bằng các chốt chặn Keyword và cơ chế xử lý Session an toàn.
