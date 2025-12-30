import os
import json
from flask import Flask, render_template, request, session, redirect, url_for

# --- CẤU HÌNH ---
base_dir = os.path.abspath(os.path.dirname(__file__))
settings_path = os.path.join(base_dir, 'data', 'settings.json')
users_path = os.path.join(base_dir, 'data', 'users.json')
template_path = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_path)
app.secret_key = 'khoa_bi_mat_cua_du_an_solar'

# --- HÀM XỬ LÝ DATA CHUNG (QUAN TRỌNG: Đừng đổi tên) ---
def load_json_file(filepath, default_data):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_data

def save_json_file(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Lỗi lưu file {filepath}: {e}")

# Dữ liệu mặc định
DEFAULT_SETTINGS = {
    "evn_bac": [1806, 1866, 2167, 2729, 3050, 3151],
    "gia_kinh_doanh": 2666, "gia_san_xuat": 1600, "tinh_thanh": {}
}
DEFAULT_USERS = {
    "admin": {"password": "admin", "role": "admin"},
    "user": {"password": "user", "role": "user"}
}

# --- HÀM TÍNH TOÁN ---
def tinh_nguoc_kwh_evn(tong_tien, settings):
    VAT = 1.08
    gia_bac = settings['evn_bac']
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

def tinh_toan_kwp(loai_hinh, gia_tri_nhap, che_do_nhap, he_so_nhap, gio_nang_tinh, settings):
    kWh = 0
    if che_do_nhap == 'theo_kwh':
        kWh = gia_tri_nhap
    else:
        tien_dien = gia_tri_nhap
        if loai_hinh == 'can_ho':
            kWh = tinh_nguoc_kwh_evn(tien_dien, settings)
        elif loai_hinh == 'kinh_doanh':
            kWh = tien_dien / settings['gia_kinh_doanh']
        elif loai_hinh == 'san_xuat':
            kWh = tien_dien / settings['gia_san_xuat']
    
    if kWh > 0 and gio_nang_tinh > 0:
        return round(((kWh * he_so_nhap) / 30) / gio_nang_tinh, 2)
    return 0

# --- ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        # Load user check
        USERS = load_json_file(users_path, DEFAULT_USERS)
        
        if user in USERS and USERS[user]['password'] == pwd:
            session['user'] = user
            session['role'] = USERS[user]['role']
            return redirect(url_for('home'))
        else:
            error = "Sai tài khoản hoặc mật khẩu!"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user' not in session: return redirect(url_for('login'))
    
    current_user = session['user']
    current_role = session.get('role', 'user')
    
    # Load Data mới nhất mỗi lần load trang
    SETTINGS = load_json_file(settings_path, DEFAULT_SETTINGS)
    USERS = load_json_file(users_path, DEFAULT_USERS)
    
    ket_qua = None
    msg_update = None
    active_tab = 'calc' # Tab mặc định

    du_lieu_nhap = {'loai_hinh': 'can_ho', 'gia_tri': '', 'che_do': 'theo_tien', 'he_so': 0.5, 'tinh_chon': ''}
    gio_nang_da_dung = 0

    if request.method == 'POST':
        # 1. ĐỔI MẬT KHẨU (Ai cũng làm được)
        if 'btn_change_pass' in request.form:
            old_pass = request.form.get('old_pass')
            new_pass = request.form.get('new_pass')
            if USERS[current_user]['password'] == old_pass:
                if new_pass:
                    USERS[current_user]['password'] = new_pass
                    save_json_file(users_path, USERS)
                    msg_update = "✅ Đổi mật khẩu thành công!"
                else: msg_update = "❌ Mật khẩu mới trống!"
            else: msg_update = "❌ Mật khẩu cũ sai!"
            active_tab = 'account'

        # 2. TẠO USER (Chỉ Admin)
        elif 'btn_add_user' in request.form and current_role == 'admin':
            new_u = request.form.get('new_username')
            new_p = request.form.get('new_password')
            new_r = request.form.get('new_role')
            if new_u and new_p:
                if new_u in USERS: msg_update = "❌ Tên đã tồn tại!"
                else:
                    USERS[new_u] = {"password": new_p, "role": new_r}
                    save_json_file(users_path, USERS)
                    msg_update = f"✅ Đã tạo {new_u} ({new_r})"
            active_tab = 'config'

        # 3. XÓA USER (Chỉ Admin)
        elif 'btn_delete_user' in request.form and current_role == 'admin':
            del_u = request.form.get('btn_delete_user')
            if del_u == 'admin': msg_update = "❌ Không xóa được Admin gốc!"
            elif del_u == current_user: msg_update = "❌ Không tự xóa mình!"
            else:
                del USERS[del_u]
                save_json_file(users_path, USERS)
                msg_update = f"🗑️ Đã xóa {del_u}"
            active_tab = 'config'

        # 4. CẬP NHẬT GIÁ (Chỉ Admin)
        elif 'btn_update_price' in request.form and current_role == 'admin':
            try:
                SETTINGS['evn_bac'] = [float(request.form.get(f'b{i}')) for i in range(1, 7)]
                SETTINGS['gia_kinh_doanh'] = float(request.form.get('gia_kd'))
                SETTINGS['gia_san_xuat'] = float(request.form.get('gia_sx'))
                save_json_file(settings_path, SETTINGS)
                msg_update = "✅ Đã lưu giá!"
            except: msg_update = "❌ Lỗi nhập số!"
            active_tab = 'config'

        # 5. THÊM TỈNH (Chỉ Admin)
        elif 'btn_add_province' in request.form and current_role == 'admin':
            t = request.form.get('new_province_name')
            try:
                h = float(request.form.get('new_province_hours'))
                SETTINGS['tinh_thanh'][t] = h
                save_json_file(settings_path, SETTINGS)
            except: pass
            active_tab = 'config'

        # 6. LƯU GIỜ NẮNG & XÓA TỈNH (Chỉ Admin)
        elif 'btn_save_list' in request.form and current_role == 'admin':
            for t in list(SETTINGS['tinh_thanh'].keys()):
                v = request.form.get(f"hours_{t}")
                if v: 
                    try: SETTINGS['tinh_thanh'][t] = float(v)
                    except: pass
            save_json_file(settings_path, SETTINGS)
            msg_update = "✅ Đã cập nhật giờ nắng!"
            active_tab = 'config'
            
        elif 'btn_delete_province' in request.form and current_role == 'admin':
            t = request.form.get('btn_delete_province')
            if t in SETTINGS['tinh_thanh']:
                del SETTINGS['tinh_thanh'][t]
                save_json_file(settings_path, SETTINGS)
            active_tab = 'config'

        # 7. TÍNH TOÁN (Ai cũng làm được)
        elif 'btn_calc' in request.form:
            try:
                lh = request.form.get('loai_hinh')
                cd = request.form.get('che_do_nhap')
                gt = float(request.form.get('gia_tri_dau_vao'))
                hs = float(request.form.get('he_so_nhap') or 0.5)
                tc = request.form.get('tinh_thanh_chon')
                gn = SETTINGS['tinh_thanh'].get(tc, 4.0)
                gio_nang_da_dung = gn
                
                du_lieu_nhap = {'loai_hinh': lh, 'gia_tri': gt, 'che_do': cd, 'he_so': hs, 'tinh_chon': tc}
                ket_qua = tinh_toan_kwp(lh, gt, cd, hs, gn, SETTINGS)
                active_tab = 'calc'
            except: pass

    return render_template('index.html', role=current_role, settings=SETTINGS, users=USERS, ket_qua=ket_qua, du_lieu_nhap=du_lieu_nhap, msg_update=msg_update, active_tab=active_tab, gio_nang_da_dung=gio_nang_da_dung)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18003)