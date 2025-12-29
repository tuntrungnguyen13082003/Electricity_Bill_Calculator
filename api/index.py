import os
import traceback
from flask import Flask, render_template, request

# --- CẤU HÌNH ĐƯỜNG DẪN ---
base_dir = os.path.abspath(os.path.dirname(__file__))
template_path = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_path)
# ---------------------------

def tinh_toan_kwp(loai_hinh, tien_dien):
    he_so = 0
    if loai_hinh == 'can_ho': he_so = 0.0005 
    elif loai_hinh == 'kinh_doanh': he_so = 0.0004
    elif loai_hinh == 'san_xuat': he_so = 0.0003
    return round(tien_dien * he_so, 2)

@app.route('/', methods=['GET', 'POST'])
def home():
    try:
        # --- CODE KIỂM TRA LỖI ---
        # Kiểm tra xem folder templates có tồn tại và có file gì bên trong
        files_in_template = "Không tìm thấy thư mục"
        if os.path.exists(template_path):
            files_in_template = str(os.listdir(template_path))
        
        # --- LOGIC CHÍNH ---
        ket_qua = None
        du_lieu_nhap = {}
        
        if request.method == 'POST':
            loai_hinh = request.form.get('loai_hinh')
            tien_dien = float(request.form.get('tien_dien'))
            du_lieu_nhap = {'loai_hinh': loai_hinh, 'tien_dien': tien_dien}
            ket_qua = tinh_toan_kwp(loai_hinh, tien_dien)

        return render_template('index.html', ket_qua=ket_qua, du_lieu_nhap=du_lieu_nhap)

    except Exception as e:
        # NẾU CÓ LỖI: In hết thông tin ra màn hình web để debug
        return f"""
        <div style="font-family: monospace; padding: 20px; background: #ffe6e6; border: 1px solid red;">
            <h2 style="color: red;">Đã bắt được lỗi!</h2>
            <p><strong>Lỗi chi tiết:</strong> {str(e)}</p>
            <hr>
            <h3>Thông tin kiểm tra đường dẫn:</h3>
            <p>1. Đường dẫn folder chứa code (base_dir): <br> {base_dir}</p>
            <p>2. Đường dẫn folder templates mong muốn: <br> {template_path}</p>
            <p>3. Các file thực tế đang có trong folder templates: <br> <strong>{files_in_template}</strong></p>
            <hr>
            <h3>Chi tiết kỹ thuật (Traceback):</h3>
            <pre>{traceback.format_exc()}</pre>
        </div>
        """

if __name__ == '__main__':
    app.run(debug=True)