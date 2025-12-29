import os
from flask import Flask, render_template, request, session, redirect, url_for

# --- CẤU HÌNH ---
base_dir = os.path.abspath(os.path.dirname(__file__))
template_path = os.path.join(base_dir, 'templates')
app = Flask(__name__, template_folder=template_path)
app.secret_key = 'khoa_bi_mat_cua_du_an_solar' 

# --- DỮ LIỆU CẤU HÌNH ---
SETTINGS = {
    'evn_bac': [1806, 1866, 2167, 2729, 3050, 3151],
    'gia_kinh_doanh': 2666,
    'gia_san_xuat': 1600,
    'so_gio_nang': 4.0 # <-- THÊM MỚI: Mặc định là 4 giờ
}

# --- HÀM TÍNH NGƯỢC TIỀN ĐIỆN (Giữ nguyên) ---
def tinh_nguoc_kwh_evn(tong_tien):
    VAT = 1.08
    gia_bac = SETTINGS['evn_bac']
    bac_thang = [
        (50, gia_bac[0] * VAT), (50, gia_bac[1] * VAT),
        (100, gia_bac[2] * VAT), (100, gia_bac[3] * VAT),
        (100, gia_bac[4] * VAT), (float('inf'), gia_bac[5] * VAT)
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
            break
    return kwh_tich_luy

# --- HÀM TÍNH TOÁN CHÍNH (ĐÃ CẬP NHẬT) ---
def tinh_toan_kwp(loai_hinh, gia_tri_nhap, che_do_nhap, he_so_nhap, gio_nang_admin):
    kWh = 0
    
    if che_do_nhap == 'theo_kwh':
        kWh = gia_tri_nhap
    else: 
        tien_dien = gia_tri_nhap
        if loai_hinh == 'can_ho':
            kWh = tinh_nguoc_kwh_evn(tien_dien)
        elif loai_hinh == 'kinh_doanh':
            kWh = tien_dien / SETTINGS['gia_kinh_doanh']
        elif loai_hinh == 'san_xuat':
            kWh = tien_dien / SETTINGS['gia_san_xuat']
    
    # CÔNG THỨC MỚI: Dùng he_so_nhap (thay 0.5) và gio_nang_admin (thay 4)
    if kWh > 0 and gio_nang_admin > 0:
        return round(((kWh * he_so_nhap) / 30) / gio_nang_admin, 2)
    return 0

# --- ROUTE ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if (user == 'admin' and pwd == 'admin') or (user == 'user' and pwd == 'user'):
            session['user'] = user
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
    if 'user' not in session: return redirect(url_for('login'))
    role = session['user']
    ket_qua = None
    msg_update = None
    active_tab = 'calc'
    
    # Thêm he_so vào dữ liệu mặc định (0.5)
    du_lieu_nhap = {
        'loai_hinh': 'can_ho', 
        'gia_tri': '', 
        'che_do': 'theo_tien',
        'he_so': 0.5 
    }

    if request.method == 'POST':
        # --- ADMIN CẬP NHẬT ---
        if 'btn_update_price' in request.form and role == 'admin':
            try:
                SETTINGS['evn_bac'] = [
                    float(request.form.get('b1')), float(request.form.get('b2')),
                    float(request.form.get('b3')), float(request.form.get('b4')),
                    float(request.form.get('b5')), float(request.form.get('b6'))
                ]
                SETTINGS['gia_kinh_doanh'] = float(request.form.get('gia_kd'))
                SETTINGS['gia_san_xuat'] = float(request.form.get('gia_sx'))
                
                # Lấy số giờ nắng từ Admin nhập
                SETTINGS['so_gio_nang'] = float(request.form.get('gio_nang'))
                
                msg_update = "✅ Đã cập nhật cấu hình thành công!"
                active_tab = 'config'
            except ValueError:
                msg_update = "❌ Lỗi nhập liệu!"
                active_tab = 'config'

        # --- TÍNH TOÁN ---
        elif 'btn_calc' in request.form:
            try:
                loai_hinh = request.form.get('loai_hinh')
                che_do = request.form.get('che_do_nhap')
                gia_tri = float(request.form.get('gia_tri_dau_vao'))
                
                # Lấy hệ số người dùng nhập (mặc định 0.5 nếu rỗng)
                he_so_input = request.form.get('he_so_nhap')
                he_so = float(he_so_input) if he_so_input else 0.5
                
                du_lieu_nhap = {'loai_hinh': loai_hinh, 'gia_tri': gia_tri, 'che_do': che_do, 'he_so': he_so}
                
                # Gọi hàm tính toán mới
                ket_qua = tinh_toan_kwp(loai_hinh, gia_tri, che_do, he_so, SETTINGS['so_gio_nang'])
                active_tab = 'calc'
            except ValueError:
                pass

    return render_template('index.html', role=role, settings=SETTINGS, ket_qua=ket_qua, du_lieu_nhap=du_lieu_nhap, msg_update=msg_update, active_tab=active_tab)

if __name__ == '__main__':
    app.run(debug=True)