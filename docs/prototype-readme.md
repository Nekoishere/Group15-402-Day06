# Prototype — AI triage Vinmec

## Mô tả
Chatbot hỏi bệnh nhân 3-5 câu về triệu chứng, gợi ý top 3 chuyên khoa phù hợp
kèm confidence score. Bệnh nhân chọn hoặc gặp lễ tân.

## Level: Mock prototype
- UI build bằng Claude Artifacts (HTML/CSS/JS)
- 1 flow chính chạy thật với Gemini API: nhập triệu chứng → nhận gợi ý khoa

## Links
- Prototype: src/docs/prototype.png


## Tools
- UI: html/css/js
- AI: claude opus 4.6 
- Prompt: system prompt + few-shot examples cho 10 triệu chứng phổ biến

## Phân công
| Thành viên | Phần | Output |
|-----------|------|--------|
| Nguyễn Công Nhật Tân |  Problem framing + product storytelling |
| Trần Nhật Minh | Edge case handling + guardrails demonstration |
| Phan Nguyễn Việt Nhân | Demo happy path + retrieval experience + value demonstration |
| Phan Anh Ly Ly | Impact analysis + evaluation metrics + admin/update thinking |
| Đồng Mạnh Hùng | User stories + solution flow + product logic |