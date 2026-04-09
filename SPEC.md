# SPEC — AI Product Hackathon


**Track:** ☐ VinFast · ☐ Vinmec · ☑ **VinUni-VinSchool** · ☐ XanhSM · ☐ Open
**Topic** : VinUni AI Academic Regulation Chatbot
**Problem statement (1 câu):** Sinh viên thường bối rối và mất thời gian chờ đợi phản hồi từ Phòng Đào tạo (PĐT) khi tra cứu quy chế học vụ, điều kiện tiên quyết, thủ tục hành chính bị phân mảnh; AI giúp tập hợp dữ liệu nội bộ và giải đáp tức thì, chính xác 24/7.

---

## 1. AI Product Canvas

|   | Value | Trust | Feasibility |
|---|-------|-------|-------------|
| **Câu hỏi** | User nào? Pain gì? AI giải gì? | Khi AI sai thì sao? User sửa bằng cách nào? | Cost/latency bao nhiêu? Risk chính? |
| **Trả lời** | *Sinh viên: Không biết tìm luật/quy chế ở đâu. PĐT: Quá tải email lặp lại. AI gom data nội bộ trả lời ngay lập tức.* | *AI trả lời kèm TRÍCH DẪN LINK GỐC. Nếu sai, sinh viên có nút "Report" gửi thẳng ticket cho PĐT để đính chính.* | *Cost: ~$0.005/query (dùng RAG + model nhẹ). Latency < 3s. Risk: Hallucinate sai điều kiện tốt nghiệp/học phí.* |

**Automation hay augmentation?** ☐ Automation · ☑ **Augmentation**
Justify: *Augmentation — Trợ lý AI cung cấp thông tin, quy chế để "tăng cường" khả năng tự lên kế hoạch của sinh viên. Các quyết định cuối cùng (đăng ký môn, nộp đơn) vẫn do sinh viên tự thực hiện. Cost of reject = 0 (nếu bot nói khó hiểu, sinh viên đọc link gốc).*

**Learning signal:**
1. User correction đi vào đâu? *Vào database logs của Dev team để tinh chỉnh chunking/retrieval của hệ thống RAG (Retrieval-Augmented Generation).*
2. Product thu signal gì để biết tốt lên hay tệ đi? *Tỷ lệ click "Thumbs up/down" trên mỗi câu trả lời; Tỷ lệ user yêu cầu "Gặp tư vấn viên thật" ngay sau khi bot trả lời.*
3. Data thuộc loại nào? ☐ User-specific · ☑ **Domain-specific** · ☐ Real-time · ☐ Human-judgment · ☐ Khác: ___
   Có marginal value không? (Model đã biết cái này chưa?) *Có marginal value cực lớn. Các mô hình LLM nền tảng (GPT, Gemini) KHÔNG THỂ biết quy chế nội bộ, cẩm nang sinh viên mới nhất của VinUni nếu không được cung cấp (Grounding).*

---

## 2. User Stories — 4 paths

### Feature: *AI Academic Advisor (Hỏi đáp quy chế & lộ trình)*

**Trigger:** *Sinh viên mở portal/app, gõ câu hỏi vào khung chat: "Em muốn học vượt môn AI nâng cao thì cần điều kiện gì?"*

| Path | Câu hỏi thiết kế | Mô tả |
|------|-------------------|-------|
| Happy — AI đúng, tự tin | User thấy gì? Flow kết thúc ra sao? | *Bot trả lời rõ các môn tiên quyết cần có, kèm link PDF Sổ tay Đào tạo trang 42. Sinh viên đọc hiểu, đóng chat.* |
| Low-confidence — AI không chắc | System báo "không chắc" bằng cách nào? User quyết thế nào? | *Sinh viên hỏi câu ghép (Vừa bảo lưu vừa chuyển ngành). Bot báo: "Câu hỏi của bạn liên quan nhiều quy trình. Bạn muốn hỏi về [Bảo lưu] trước hay [Chuyển ngành] trước?"* |
| Failure — AI sai | User biết AI sai bằng cách nào? Recover ra sao? | *Bot lấy nhầm quy chế năm cũ báo sinh viên đủ điều kiện ra trường. Sinh viên cross-check với cố vấn học tập thấy sai → Mất niềm tin.* |
| Correction — user sửa | User sửa bằng cách nào? Data đó đi vào đâu? | *Sinh viên bấm "Báo cáo lỗi nội dung". Ticket đẩy về PĐT. PĐT phát hiện file PDF quy chế mới chưa được sync vào cơ sở dữ liệu của AI → Update lại DB.* |

---

## 3. Eval metrics + threshold

**Optimize precision hay recall?** ☑ **Precision** · ☐ Recall
Tại sao? *Đối với môi trường giáo dục/học vụ, sự chính xác (Precision) là tối thượng. Thà bot trả lời "Tôi không tìm thấy thông tin, bạn vui lòng liên hệ Phòng Đào tạo" (Low Recall) còn hơn là bot "bịa" ra thông tin sai (Low Precision) khiến sinh viên hiểu lầm về học bổng, dẫn đến trượt môn hoặc mất tiền.*

| Metric | Threshold | Red flag (dừng khi) |
|--------|-----------|---------------------|
| *Resolution Rate (Tự giải quyết không cần người thật)* | *≥ 60%* | *< 40% trong 2 tuần liên tiếp* |
| *Retrieval Accuracy (Trích xuất đúng tài liệu gốc)* | *≥ 95%* | *< 85% (Hệ thống tìm kiếm nội bộ đang hỏng)* |
| *Hallucination Rate (Tỷ lệ tự bịa câu trả lời)* | *< 2%* | *> 5% (Phải tạm tắt bot để rà soát prompt)* |

---

## 4. Top 3 failure modes

*Lưu ý: Nguy hiểm nhất là khi user không biết hệ thống đang sai mà vẫn tin tưởng làm theo.*

| # | Trigger | Hậu quả | Mitigation |
|---|---------|---------|------------|
| 1 | *Sinh viên hỏi về chính sách học bổng/học phí.* | *AI tự tổng hợp số liệu sai (hallucinate), sinh viên tin theo và chuẩn bị sai ngân sách.* | *Tạo Rule: Các intent (ý định) liên quan đến tiền bạc/học bổng -> AI KHÔNG được sinh text, chỉ được văng Link bài viết chính thức.* |
| 2 | *PĐT thay đổi quy định mới nhưng chưa update Vector DB của bot.* | *AI trả lời cực kỳ tự tin bằng data năm ngoái. User tin sái cổ vì bot trích dẫn rất mạch lạc.* | *Xây dựng pipeline tự động: Mỗi khi web trường/portal cập nhật file mới, webhook tự trigger để update lại DB của bot ngay lập tức.* |
| 3 | *Sinh viên nhắn tin tiêu cực (căng thẳng, trầm cảm, cảnh báo học vụ).* | *AI trả lời bằng tone giọng vô cảm, máy móc gây tổn thương tâm lý.* | *Detect sentiment (phân tích cảm xúc). Nếu phát hiện keyword rủi ro cao -> Sang tay (handoff) lập tức cho bộ phận Tư vấn tâm lý sinh viên.* |


## 6. Mini AI spec (1 trang) - Cả team

**Sản phẩm:** VinUni AI Academic Regulation Chatbot
**Dành cho:** Sinh viên (đặc biệt là tân sinh viên) và Cán bộ Phòng Đào tạo (PĐT).

**Product Giải Quyết Gì?**
Xóa bỏ nút thắt cổ chai trong luồng thông tin học vụ. Hiện tại, sinh viên gặp khó trong việc tra cứu hàng chục trang quy chế PDF hoặc phải chờ 1-2 ngày để PĐT rep email. AI Advisor đóng vai trò như một thủ thư thông minh, đọc hiểu toàn bộ quy chế và trả lời tức thì, có trích dẫn minh bạch.

**AI Làm Gì? (Augmentation)**
Ứng dụng kiến trúc RAG (Retrieval-Augmented Generation). Thay vì để AI tự do sáng tạo, hệ thống sẽ giới hạn AI chỉ được phép đọc và tổng hợp thông tin từ nguồn Dữ liệu Đóng (các file PDF, FAQ, syllabus của trường). AI hoạt động ở mức Augmentation: nó mớm thông tin chuẩn xác, sinh viên dựa vào đó tự ra quyết định học tập (ví dụ: đăng ký tín chỉ trên hệ thống quản lý học tập). Giao diện có thể tích hợp mượt mà vào các nền tảng web hiện hữu của trường.

**Chất Lượng (Optimize for Precision)**
Hệ thống ưu tiên tuyệt đối tính chính xác (Precision). Nguyên tắc: "Không biết thì bảo không biết, tuyệt đối không bịa". Mọi câu trả lời phải có link reference.
