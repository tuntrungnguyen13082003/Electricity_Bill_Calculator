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
    # DANH SÁCH TỈNH THÀNH VÀ GIỜ NẮNG (Mặc định)
    'tinh_thanh': {
        'Hà Nội': 3.2,
        'Đà Nẵng': 4.5,
        'TP. Hồ Chí Minh': 4.6,
        'Cần Thơ': 4.8,
        'Ninh Thuận': 5.2
    }
}

# --- HÀM TÍNH TOÁN ---
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

def tinh_toan_kwp(loai_hinh, gia_tri_nhap, che_do_nhap, he_so_nhap, gio_nang_tinh):
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
    
    # CÔNG THỨC: Dùng gio_nang_tinh được truyền vào
    if kWh > 0 and gio_nang_tinh > 0:
        return round(((kWh * he_so_nhap) / 30) / gio_nang_tinh, 2)
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
    
    # Dữ liệu mặc định form nhập
    du_lieu_nhap = {
        'loai_hinh': 'can_ho', 'gia_tri': '', 'che_do': 'theo_tien', 'he_so': 0.5, 'tinh_chon': ''
    }
    # Lấy thông tin giờ nắng của tỉnh đang chọn để hiển thị ra kết quả
    gio_nang_da_dung = 0 

    if request.method == 'POST':
        # --- ADMIN: CẬP NHẬT GIÁ CƠ BẢN ---
        if 'btn_update_price' in request.form and role == 'admin':
            try:
                SETTINGS['evn_bac'] = [
                    float(request.form.get('b1')), float(request.form.get('b2')),
                    float(request.form.get('b3')), float(request.form.get('b4')),
                    float(request.form.get('b5')), float(request.form.get('b6'))
                ]
                SETTINGS['gia_kinh_doanh'] = float(request.form.get('gia_kd'))
                SETTINGS['gia_san_xuat'] = float(request.form.get('gia_sx'))
                msg_update = "✅ Đã cập nhật giá điện cơ bản!"
                active_tab = 'config'
            except ValueError:
                msg_update = "❌ Lỗi nhập liệu giá!"
                active_tab = 'config'
        
        # --- ADMIN: THÊM TỈNH MỚI ---
        elif 'btn_add_province' in request.form and role == 'admin':
            ten_moi = request.form.get('new_province_name')
            gio_moi = float(request.form.get('new_province_hours'))
            if ten_moi and gio_moi > 0:
                SETTINGS['tinh_thanh'][ten_moi] = gio_moi
                msg_update = f"✅ Đã thêm tỉnh {ten_moi}!"
            active_tab = 'config'

        # --- ADMIN: XÓA TỈNH ---
        elif 'btn_delete_province' in request.form and role == 'admin':
            ten_xoa = request.form.get('delete_name')
            if ten_xoa in SETTINGS['tinh_thanh']:
                del SETTINGS['tinh_thanh'][ten_xoa]
                msg_update = f"🗑️ Đã xóa tỉnh {ten_xoa}!"
            active_tab = 'config'

        # --- USER: TÍNH TOÁN ---
        elif 'btn_calc' in request.form:
            try:
                loai_hinh = request.form.get('loai_hinh')
                che_do = request.form.get('che_do_nhap')
                gia_tri = float(request.form.get('gia_tri_dau_vao'))
                he_so = float(request.form.get('he_so_nhap') or 0.5)
                
                # Lấy tên tỉnh và tra cứu giờ nắng
                tinh_chon = request.form.get('tinh_thanh_chon')
                gio_nang = SETTINGS['tinh_thanh'].get(tinh_chon, 4.0) # Mặc định 4 nếu lỗi
                gio_nang_da_dung = gio_nang

                du_lieu_nhap = {
                    'loai_hinh': loai_hinh, 'gia_tri': gia_tri, 
                    'che_do': che_do, 'he_so': he_so, 'tinh_chon': tinh_chon
                }
                
                ket_qua = tinh_toan_kwp(loai_hinh, gia_tri, che_do, he_so, gio_nang)
                active_tab = 'calc'
            except ValueError:
                pass

    return render_template('index.html', role=role, settings=SETTINGS, ket_qua=ket_qua, du_lieu_nhap=du_lieu_nhap, msg_update=msg_update, active_tab=active_tab, gio_nang_da_dung=gio_nang_da_dung)

if __name__ == '__main__':
    app.run(debug=True)