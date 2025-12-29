import os
from flask import Flask, render_template, request

# --- KHẮC PHỤC LỖI KHÔNG TÌM THẤY TEMPLATES TRÊN VERCEL ---
# Lấy đường dẫn tuyệt đối của file index.py hiện tại
base_dir = os.path.dirname(os.path.abspath(__file__))
# Trỏ ngược ra thư mục cha (root) rồi vào thư mục templates
template_dir = os.path.join(base_dir, '..', 'templates')

# Khởi tạo Flask với đường dẫn tuyệt đối vừa tạo
app = Flask(__name__, template_folder=template_dir)
# ----------------------------------------------------------

def tinh_toan_kwp(loai_hinh, tien_dien):
    # --- CÔNG THỨC GIẢ ĐỊNH ---
    he_so = 0
    if loai_hinh == 'can_ho':
        he_so = 0.0005 
    elif loai_hinh == 'kinh_doanh':
        he_so = 0.0004
    elif loai_hinh == 'san_xuat':
        he_so = 0.0003
    
    kwp = tien_dien * he_so
    return round(kwp, 2)

@app.route('/', methods=['GET', 'POST'])
def home():
    ket_qua = None
    du_lieu_nhap = {}

    if request.method == 'POST':
        try:
            loai_hinh = request.form.get('loai_hinh')
            tien_dien = float(request.form.get('tien_dien'))
            du_lieu_nhap = {'loai_hinh': loai_hinh, 'tien_dien': tien_dien}
            ket_qua = tinh_toan_kwp(loai_hinh, tien_dien)
        except ValueError:
            ket_qua = "Lỗi nhập liệu"

    return render_template('index.html', ket_qua=ket_qua, du_lieu_nhap=du_lieu_nhap)

# Vercel cần app này để chạy
if __name__ == '__main__':
    app.run(debug=True)