+import os
from flask import Flask, render_template, request, session, redirect, url_for

# --- CẤU HÌNH ---
base_dir = os.path.abspath(os.path.dirname(__file__))
template_path = os.path.join(base_dir, 'templates')
app = Flask(__name__, template_folder=template_path)

# Cần secret_key để chạy tính năng đăng nhập (session)
app.secret_key = 'khoa_bi_mat_cua_du_an_solar' 

# --- DỮ LIỆU CẤU HÌNH MẶC ĐỊNH (DATABASE GIẢ LẬP) ---
# Đây là nơi lưu giá điện mà Admin có thể chỉnh sửa
SETTINGS = {
    'evn_bac': [1806, 1866, 2167, 2729, 3050, 3151], # 6 bậc
    'gia_kinh_doanh': 2666, # Giá mặc định
    'gia_san_xuat': 1600    # Giá mặc định
}

# --- HÀM TÍNH TOÁN ---
def tinh_nguoc_kwh_evn(tong_tien):
    VAT = 1.08
    # Lấy giá từ cấu hình hiện tại (SETTINGS) thay vì fix cứng
    gia_bac = SETTINGS['evn_bac']
    
    bac_thang = [
        (50, gia_bac[0] * VAT),
        (50, gia_bac[1] * VAT),
        (100, gia_bac[2] * VAT),
        (100, gia_bac[3] * VAT),
        (100, gia_bac[4] * VAT),
        (float('inf'), gia_bac[5] * VAT)
    ]

    kwh_tich_luy = 0
    tien_con_lai = tong_tien

    for so_kwh_cua_bac, don_gia in bac_thang:
        tien_max_cua_bac = so_kwh_cua_bac * don_gia
        if tien_con_lai > tien_max_cua_bac:
            kwh_tich_luy += so_kwh_cua_bac
            tien_con_lai -= tien_max_cua_bac
        else:
            kwh_tich_luy += tien_con_lai / don_gia
            tien_con_lai = 0
            break
    return kwh_tich_luy

def tinh_toan_kwp(loai_hinh, tien_dien):
    kWh = 0
    if loai_hinh == 'can_ho':
        kWh = tinh_nguoc_kwh_evn(tien_dien)
    elif loai_hinh == 'kinh_doanh':
        # Lấy giá admin đã cài
        kWh = tien_dien / SETTINGS['gia_kinh_doanh']
    elif loai_hinh == 'san_xuat':
        # Lấy giá admin đã cài
        kWh = tien_dien / SETTINGS['gia_san_xuat']
    
    # Công thức kWp
    if kWh > 0:
        return round(((kWh * 0.5) / 30) / 4, 2) # Chia 4 giờ nắng (ví dụ)
    return 0

# --- CÁC ROUTE (ĐƯỜNG DẪN) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        # Kiểm tra tài khoản
        if user == 'admin' and pwd == 'admin':
            session['user'] = 'admin'
            return redirect(url_for('home'))
        elif user == 'user' and pwd == 'user':
            session['user'] = 'user'
            return redirect(url_for('home'))
        else:
            error = "Sai tài khoản hoặc mật khẩu!"
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def home():
    # Chưa đăng nhập thì đá về trang login
    if 'user' not in session:
        return redirect(url_for('login'))
    
    role = session['user'] # Lấy quyền (admin hay user)
    ket_qua = None
    du_lieu_nhap = {}
    msg_update = None

    if request.method == 'POST':
        # XỬ LÝ 1: ADMIN CẬP NHẬT GIÁ
        if 'btn_update_price' in request.form and role == 'admin':
            try:
                # Cập nhật vào biến toàn cục SETTINGS
                SETTINGS['evn_bac'] = [
                    float(request.form.get('b1')), float(request.form.get('b2')),
                    float(request.form.get('b3')), float(request.form.get('b4')),
                    float(request.form.get('b5')), float(request.form.get('b6'))
                ]
                SETTINGS['gia_kinh_doanh'] = float(request.form.get('gia_kd'))
                SETTINGS['gia_san_xuat'] = float(request.form.get('gia_sx'))
                msg_update = "✅ Đã cập nhật giá điện thành công!"
            except ValueError:
                msg_update = "❌ Lỗi nhập liệu cấu hình!"

        # XỬ LÝ 2: TÍNH TOÁN (Dành cho cả Admin và User)
        elif 'btn_calc' in request.form:
            try:
                loai_hinh = request.form.get('loai_hinh')
                tien_dien = float(request.form.get('tien_dien'))
                du_lieu_nhap = {'loai_hinh': loai_hinh, 'tien_dien': tien_dien}
                ket_qua = tinh_toan_kwp(loai_hinh, tien_dien)
            except ValueError:
                pass

    return render_template('index.html', 
                           role=role, 
                           settings=SETTINGS, 
                           ket_qua=ket_qua, 
                           du_lieu_nhap=du_lieu_nhap,
                           msg_update=msg_update)

if __name__ == '__main__':
    app.run(debug=True)