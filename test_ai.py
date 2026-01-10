import google.generativeai as genai
import os

# --- CẤU HÌNH (Thay Key của bạn vào đây) ---
MY_KEY = "AIzaSyAkDousFLZy33pXCo3by3zZ8ar3Pphuy0c" 

os.environ["GOOGLE_API_KEY"] = MY_KEY
genai.configure(api_key=MY_KEY)

def kiem_tra():
    print("1. Đang kết nối tới Google AI...")
    try:
        # Gọi thử model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Hỏi một câu đơn giản (không cần ảnh) để test mạng và Key
        response = model.generate_content("Chào bạn, hãy trả lời 'OK' nếu bạn nhận được tin nhắn này.")
        
        print("\n--- KẾT QUẢ ---")
        print(f"✅ Thành công! AI trả lời: {response.text}")
        print("----------------")
        
    except Exception as e:
        print("\n❌ LỖI RỒI BẠN ƠI!")
        print(f"Chi tiết lỗi: {e}")

if __name__ == "__main__":
    kiem_tra()