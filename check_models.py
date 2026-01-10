import requests
import os

# --- THAY KEY CỦA BẠN VÀO ĐÂY ---
MY_API_KEY = "AIzaSyAkDousFLZy33pXCo3by3zZ8ar3Pphuy0c" 

def lay_danh_sach_model():
    print("dang ket noi de lay danh sach model...")
    
    # Gọi hàm list models
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={MY_API_KEY}"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ DANH SÁCH CÁC MODEL KHẢ DỤNG:")
            tim_thay = False
            for m in data.get('models', []):
                # Chỉ in ra những model hỗ trợ tạo nội dung (generateContent)
                if 'generateContent' in m['supportedGenerationMethods']:
                    print(f"  - {m['name']}") # Ví dụ: models/gemini-1.5-flash
                    tim_thay = True
            
            if not tim_thay:
                print("⚠️ Không tìm thấy model nào hỗ trợ generateContent. Key có thể bị giới hạn.")
        else:
            print(f"\n❌ LỖI KHI LẤY DANH SÁCH: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"Lỗi Code: {e}")

if __name__ == "__main__":
    lay_danh_sach_model()