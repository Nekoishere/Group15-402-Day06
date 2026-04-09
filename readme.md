# 1. Cài đặt venv và cài requirements trong requirements.txt
```
cd c:/GET_A_JOB/VIN_AI/Lab/Day06
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

# 2. Tạo file .env từ .env.example
Thêm OpenAI API key của bạn. 
OPENAI_API_KEY=sk-...your-key-here...

# 3. Chạy ứng dụng
```
python app.py
```
Sau đó mở trình duyệt vào: http://localhost:5000

#Đăng nhập bằng tài khoản trong .env để có quyền admin, giúp thêm và xóa các file PDF regulations. 
