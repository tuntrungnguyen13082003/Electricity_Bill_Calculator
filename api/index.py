import os
from flask import Flask, render_template, request

# --- CẤU HÌNH ĐƯỜNG DẪN CHUẨN ---
base_dir = os.path.abspath(os.path.dirname(__file__))
template_path = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_path)

# --- HÀM TÍNH TOÁN (Logic của bạn nằm ở đây) ---
def tinh_toan_kwp(loai_hinh, tien_dien):
    # Bạn có thể thay đổi công thức thoải mái tại đây
    he_so = 0
    if loai_hinh == 'can_ho':
        he_so = 0.0005 
    elif loai_hinh == 'kinh_doanh':
        he_so = 0.0004
    elif loai_hinh == 'san_xuat':
        he_so = 0.0003
    
    kwp = tien_dien * he_so
    return round(kwp, 2)
# -----------------------------------------------

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
            pass # Nếu nhập lỗi thì chỉ reload trang

    return render_template('index.html', ket_qua=ket_qua, du_lieu_nhap=du_lieu_nhap)

if __name__ == '__main__':
    app.run(debug=True)