import os
import json
import pandas as pd
from datetime import datetime, timedelta # Thêm timedelta
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, send_file

# --- CẤU HÌNH ---
base_dir = os.path.abspath(os.path.dirname(__file__))
settings_path = os.path.join(base_dir, 'data', 'settings.json')
users_path = os.path.join(base_dir, 'data', 'users.json')
excel_path = os.path.join(base_dir, 'data', 'tinh_thanh.xlsx')
history_path = os.path.join(base_dir, 'data', 'lich_su_khach_hang.xlsx')
template_path = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_path)
app.secret_key = 'khoa_bi_mat_cua_du_an_solar'

# --- HÀM XỬ LÝ EXCEL (ĐỌC) ---
def load_excel_provinces():
    default_data = {"Hà Nội": 3.8, "TP. HCM": 4.5}
    try:
        if not os.path.exists(excel_path): return default_data
        df = pd.read_excel(excel_path)
        df.columns = df.columns.str.strip()
        if 'Ten_Tinh' not in df.columns or 'Gio_Nang' not in df.columns: return default_data
        df = df.dropna(subset=['Ten_Tinh', 'Gio_Nang'])
        df['Gio_Nang'] = df['Gio_Nang'].astype(str).str.replace(',', '.', regex=False)
        df['Gio_Nang'] = pd.to_numeric(df['Gio_Nang'], errors='coerce') 
        df = df.dropna(subset=['Gio_Nang'])
        return pd.Series(df.Gio_Nang.values, index=df.Ten_Tinh).to_dict()
    except: return default_data

# --- HÀM XỬ LÝ EXCEL (GHI) ---
def save_excel_provinces(dict_data):
    try:
        df = pd.DataFrame(list(dict_data.items()), columns=['Ten_Tinh', 'Gio_Nang'])
        df.to_excel(excel_path, index=False)
    except: pass

# --- HÀM XỬ LÝ JSON ---
def load_json_file(filepath, default_data):
    try:
        with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
    except: return default_data

def save_json_file(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

# Dữ liệu mặc định
DEFAULT_SETTINGS = { 
    "evn_bac": [1806, 1866, 2167, 2729, 3050, 3151], 
    "gia_kinh_doanh": 2666, "gia_san_xuat": 1600, "tinh_thanh": {}, "dien_tich_kwp": 4.5,
    "he_so_nhom": { 
        "gd_co_nguoi": 0.2, "gd_di_lam": 0.15, "gd_ban_dem": 0.15, 
        "kd_min": 0.1, "kd_max": 0.25,
        "sx_min": 0.1, "sx_max": 0.25
    }
}
DEFAULT_USERS = { "admin": {"password": "admin", "role": "admin"}, "user": {"password": "user", "role": "user"} }

# --- HÀM TÍNH TOÁN ---
def tinh_nguoc_kwh_evn(tong_tien, settings):
    VAT = 1.08
    gia_bac = settings.get('evn_bac', DEFAULT_SETTINGS['evn_bac'])
    bac_thang = [(50, gia_bac[0]*VAT), (50, gia_bac[1]*VAT), (100, gia_bac[2]*VAT), (100, gia_bac[3]*VAT), (100, gia_bac[4]*VAT), (float('inf'), gia_bac[5]*VAT)]
    kwh, tien = 0, tong_tien
    for so_kwh, don_gia in bac_thang:
        tien_max = so_kwh * don_gia
        if tien > tien_max: kwh += so_kwh; tien -= tien_max
        else: kwh += tien / don_gia; break
    return kwh

def tinh_toan_kwp(loai_hinh, gia_tri_nhap, che_do_nhap, he_so_form, gio_nang_tinh, settings):
    kWh = 0
    if che_do_nhap == 'theo_kwh': kWh = gia_tri_nhap
    else:
        if loai_hinh == 'can_ho': kWh = tinh_nguoc_kwh_evn(gia_tri_nhap, settings)
        elif loai_hinh == 'kinh_doanh': kWh = gia_tri_nhap / settings.get('gia_kinh_doanh', 2666)
        elif loai_hinh == 'san_xuat': kWh = gia_tri_nhap / settings.get('gia_san_xuat', 1600)
    
    if kWh <= 0 or gio_nang_tinh <= 0: return [0, 0]

    # Hàm tính nội bộ
    def calc(hs):
        res = ((kWh * hs) / 30) / gio_nang_tinh
        return round(max(res, 1.0), 2)

    hs_data = settings.get('he_so_nhom', {})
    
    if loai_hinh == 'can_ho':
        val = calc(he_so_form)
        return [val, val]
    elif loai_hinh == 'kinh_doanh':
        return [calc(hs_data.get('kd_min', 0.2)), calc(hs_data.get('kd_max', 0.3))]
    elif loai_hinh == 'san_xuat':
        return [calc(hs_data.get('sx_min', 0.2)), calc(hs_data.get('sx_max', 0.3))]
    
    return [0, 0]

# --- ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        USERS = load_json_file(users_path, DEFAULT_USERS)
        if user in USERS and USERS[user]['password'] == pwd:
            session['user'], session['role'] = user, USERS[user]['role']
            return redirect(url_for('home', init=1))
        error = "Sai tài khoản hoặc mật khẩu!"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user' not in session: return redirect(url_for('login'))
    
    current_user, current_role = session['user'], session.get('role', 'user')
    SETTINGS = load_json_file(settings_path, DEFAULT_SETTINGS)
    SETTINGS['tinh_thanh'] = load_excel_provinces()
    USERS = load_json_file(users_path, DEFAULT_USERS)
    
    ket_qua, msg_update = None, None
    dien_tich = None
    active_tab = request.args.get('active_tab', 'calc')
    
    du_lieu_nhap = {
        'loai_hinh': 'can_ho', 'gia_tri': '', 'che_do': 'theo_tien', 
        'he_so': 0.5, 'tinh_chon': '', 'ten_kh': '', 'ngu_canh': 'gd_di_lam'
    }
    gio_nang_da_dung = 0

    if request.method == 'POST':
        # 1. ĐỔI PASS
        if 'btn_change_pass' in request.form:
            op, np = request.form.get('old_pass'), request.form.get('new_pass')
            if USERS[current_user]['password'] == op:
                USERS[current_user]['password'] = np; save_json_file(users_path, USERS)
                msg_update = "✅ Đổi pass thành công!"
            else: msg_update = "❌ Pass cũ sai!"
            active_tab = 'account'

        # 2. QUẢN LÝ USER
        elif 'btn_add_user' in request.form and current_role == 'admin':
            nu, np, nr = request.form.get('new_username'), request.form.get('new_password'), request.form.get('new_role')
            if nu and np:
                if nu in USERS: msg_update = "❌ Tên trùng!"
                else: USERS[nu] = {"password": np, "role": nr}; save_json_file(users_path, USERS); msg_update = f"✅ Tạo {nu} xong!"
            active_tab = 'users'
        
        elif 'btn_delete_user' in request.form and current_role == 'admin':
            del_u = request.form.get('btn_delete_user')
            if del_u not in ['admin', current_user]: del USERS[del_u]; save_json_file(users_path, USERS)
            active_tab = 'users'

        # 3. CẬP NHẬT GIÁ
        elif 'btn_update_price' in request.form and current_role == 'admin':
            try:
                def get_float(key, default=0):
                    val = request.form.get(key, str(default))
                    if not val: return default
                    return float(val.replace(',', '.'))

                SETTINGS['evn_bac'] = [get_float(f'b{i}') for i in range(1, 7)]
                SETTINGS['gia_kinh_doanh'] = get_float('gia_kd')
                SETTINGS['gia_san_xuat'] = get_float('gia_sx')
                SETTINGS['dien_tich_kwp'] = get_float('dien_tich_kwp', 4.5)
                
                if 'he_so_nhom' not in SETTINGS: SETTINGS['he_so_nhom'] = {}
                
                for k in ['gd_co_nguoi', 'gd_di_lam', 'gd_ban_dem']:
                    raw = get_float(f'hs_{k}')
                    SETTINGS['he_so_nhom'][k] = min(1.0, max(0.0, raw))

                for k in ['kd_min', 'kd_max', 'sx_min', 'sx_max']:
                    raw = get_float(f'hs_{k}')
                    SETTINGS['he_so_nhom'][k] = min(1.0, max(0.0, raw))
                    
                save_json_file(settings_path, {k:v for k,v in SETTINGS.items() if k != 'tinh_thanh'})
                msg_update = "✅ Đã lưu giá!"
            except Exception as e: 
                print(f"Lỗi update price: {e}") 
                msg_update = "❌ Lỗi nhập số!"
            active_tab = 'config'
        
        # 4. QUẢN LÝ TỈNH
        elif 'btn_add_province' in request.form and current_role == 'admin':
            t, h = request.form.get('new_province_name'), request.form.get('new_province_hours')
            try: SETTINGS['tinh_thanh'][t] = float(h); save_excel_provinces(SETTINGS['tinh_thanh'])
            except: pass
            active_tab = 'config'
        elif 'btn_save_list' in request.form and current_role == 'admin':
            for t in list(SETTINGS['tinh_thanh'].keys()):
                v = request.form.get(f"hours_{t}")
                if v: SETTINGS['tinh_thanh'][t] = float(v)
            save_excel_provinces(SETTINGS['tinh_thanh']); active_tab = 'config'
        elif 'btn_delete_province' in request.form and current_role == 'admin':
            t = request.form.get('btn_delete_province')
            if t in SETTINGS['tinh_thanh']: del SETTINGS['tinh_thanh'][t]; save_excel_provinces(SETTINGS['tinh_thanh'])
            active_tab = 'config'
        elif 'btn_upload_excel' in request.form and current_role == 'admin':
            f = request.files.get('file_excel')
            if f and f.filename.endswith('.xlsx'):
                try: f.save(excel_path); SETTINGS['tinh_thanh'] = load_excel_provinces(); msg_update = "✅ Upload OK!"
                except: msg_update = "❌ Lỗi file!"
            active_tab = 'config'
        
        elif 'btn_upload_history' in request.form and current_role == 'admin':
            if 'file_history' not in request.files: msg_update = "❌ Chưa chọn file!"
            else:
                file = request.files['file_history']
                if file and file.filename.endswith('.xlsx'):
                    try: file.save(history_path); msg_update = "✅ Đã cập nhật file Lịch Sử!"; active_tab = 'history'
                    except Exception as e: msg_update = f"❌ Lỗi: {e}"

        # 5. TÍNH TOÁN CÔNG SUẤT (DỰ TOÁN)
        elif 'btn_calc' in request.form:
            try:
                ten_kh = request.form.get('ten_khach_hang', 'Khách vãng lai')
                lh, cd = request.form.get('loai_hinh'), request.form.get('che_do_nhap')
                ngu_canh = request.form.get('ngu_canh_chon')
                
                raw_gt = request.form.get('gia_tri_dau_vao', '0')
                gt = float(raw_gt.replace('.', ''))
                hs = float(request.form.get('he_so_nhap') or 0.5)
                tc = request.form.get('tinh_thanh_chon')
                gn = SETTINGS['tinh_thanh'].get(tc, 4.0); gio_nang_da_dung = gn
                
                du_lieu_nhap.update({'loai_hinh': lh, 'gia_tri': raw_gt, 'che_do': cd, 'he_so': hs, 'tinh_chon': tc, 'ten_kh': ten_kh, 'ngu_canh': ngu_canh})
                
                kwp_list = tinh_toan_kwp(lh, gt, cd, hs, gn, SETTINGS)
                kwp_min, kwp_max = kwp_list[0], kwp_list[1]
                he_so_dt = SETTINGS.get('dien_tich_kwp', 4.5)
                
                if kwp_min == kwp_max:
                    ket_qua = f"{kwp_min}"
                    dien_tich = f"≈ {round(kwp_min * he_so_dt, 1)}"
                    excel_res = f"{kwp_min} kWp (≈{round(kwp_min * he_so_dt, 1)} m²)"
                else:
                    ket_qua = f"{kwp_min} ➔ {kwp_max}"
                    dt_min = round(kwp_min * he_so_dt, 1)
                    dt_max = round(kwp_max * he_so_dt, 1)
                    dien_tich = f"{dt_min} ➔ {dt_max}"
                    excel_res = f"{kwp_min}-{kwp_max} kWp (≈{dt_min}-{dt_max} m²)"
                
                try:
                    map_sheet = {'can_ho': 'Hộ Gia Đình', 'kinh_doanh': 'Kinh Doanh', 'san_xuat': 'Sản Xuất'}
                    ten_sheet = map_sheet.get(lh, 'Khác')
                    thoi_gian = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    new_row = pd.DataFrame([{
                        "Tên Khách Hàng": ten_kh, "Thời Gian": thoi_gian, 
                        "Khu Vực": f"{tc} - {ten_sheet}", 
                        "Đầu Vào": f"{raw_gt} {'VNĐ' if cd=='theo_tien' else 'kWh'}/Month", 
                        "Kết Quả (kWp)": excel_res
                    }])
                    
                    all_sheets = pd.read_excel(history_path, sheet_name=None) if os.path.exists(history_path) else {}
                    if ten_sheet in all_sheets: 
                        all_sheets[ten_sheet] = pd.concat([all_sheets[ten_sheet], new_row], ignore_index=True)
                    else: all_sheets[ten_sheet] = new_row
                    
                    with pd.ExcelWriter(history_path) as writer:
                        for s_name, data in all_sheets.items(): data.to_excel(writer, sheet_name=s_name, index=False)
                except Exception as e: print(f"Lỗi lưu: {e}")
                
                active_tab = 'calc'
            except: pass

# 6. TÍNH BIỂU ĐỒ PHỤ TẢI (BẢN FIX LỖI KEY ERROR)
        elif 'btn_calc_load' in request.form:
            try:
                # --- A. HÀM HỖ TRỢ ---
                def get_float_safe(key):
                    val = request.form.get(key, '')
                    return float(val) if val and val.strip() else 0.0

                def get_hour_safe(key, default_h):
                    val = request.form.get(key)
                    if not val or ':' not in val: return default_h
                    try: return int(val.split(':')[0])
                    except: return default_h

                # --- B. LẤY INPUT ---
                kwh_cd = get_float_safe('kwh_cd')
                kwh_td = get_float_safe('kwh_td')
                kwh_bt = get_float_safe('kwh_bt')
                
                d_start = request.form.get('ngay_dau')
                d_end = request.form.get('ngay_cuoi')
                h_start = get_hour_safe('gio_lam_tu', 8)
                h_end = get_hour_safe('gio_lam_den', 17)

                list_ngay_nghi_str = request.form.getlist('ngay_nghi')
                list_ngay_nghi = [int(x) for x in list_ngay_nghi_str] if list_ngay_nghi_str else []

                du_lieu_nhap.update({
                    'kwh_cd': kwh_cd, 'kwh_td': kwh_td, 'kwh_bt': kwh_bt,
                    'ngay_dau': d_start, 'ngay_cuoi': d_end,
                    'gio_lam_tu': request.form.get('gio_lam_tu'),
                    'gio_lam_den': request.form.get('gio_lam_den'),
                    'list_ngay_nghi': list_ngay_nghi
                })

                if d_start and d_end:
                    date_format = "%Y-%m-%d"
                    try:
                        start_date = datetime.strptime(d_start, date_format)
                        end_date = datetime.strptime(d_end, date_format)
                        total_days = (end_date - start_date).days + 1
                    except: total_days = 0
                    
                    if total_days > 0:
                        # --- C. PHÂN LOẠI CHI TIẾT SỐ NGÀY ---
                        count_days = {
                            'total': total_days, 
                            'week_work': 0, 'sun_work': 0, 
                            'off_weekday': 0, 'off_sunday': 0
                        }
                        
                        for i in range(total_days):
                            current_day = start_date + timedelta(days=i)
                            wd = current_day.weekday() # 0=T2...6=CN
                            
                            if wd in list_ngay_nghi:
                                if wd == 6: count_days['off_sunday'] += 1
                                else: count_days['off_weekday'] += 1
                            else:
                                if wd == 6: count_days['sun_work'] += 1
                                else: count_days['week_work'] += 1
                        
                        # Tổng số ngày nghỉ
                        total_off_days = count_days['off_weekday'] + count_days['off_sunday']

                        # --- D. TÍNH TẢI NỀN ---
                        avg_total_day_td = kwh_td / total_days
                        p_base = avg_total_day_td / 6 if avg_total_day_td > 0 else 0

                        # --- E. PHÂN TÍCH CA LÀM VIỆC ---
                        hours_cd_in_shift = 0 
                        hours_bt_in_shift = 0
                        real_h_end = max(h_start + 1, h_end)
                        
                        for h in range(h_start, real_h_end):
                            if h in [22, 23, 0, 1, 2, 3]: pass 
                            elif h == 10 or h in [17, 18, 19]: hours_cd_in_shift += 1
                            elif h == 9 or h == 11: 
                                hours_cd_in_shift += 0.5; hours_bt_in_shift += 0.5
                            else: hours_bt_in_shift += 1

                        # --- F. TÍNH CÔNG SUẤT MÁY (P_ADD) ---
                        
                        # Xác định các cờ báo (Flags)
                        is_sun_work = count_days['sun_work'] > 0
                        is_sun_off = 6 in list_ngay_nghi
                        # Có nghỉ ngày thường hay không
                        has_weekday_off = count_days['off_weekday'] > 0

                        # ===============================
                        # A. CAO ĐIỂM
                        # ===============================
                        total_hours_cd_run = hours_cd_in_shift * count_days['week_work']
                        base_kwh_cd = p_base * 5 * count_days['week_work']
                        prod_kwh_cd = max(0, kwh_cd - base_kwh_cd)

                        p_add_cd = prod_kwh_cd / total_hours_cd_run if total_hours_cd_run > 0 else 0

                        # ===============================
                        # B. XỬ LÝ THẤP ĐIỂM CHO NGÀY NGHỈ (TH3)
                        # ===============================
                        if is_sun_work and has_weekday_off:
                            # Dùng thấp điểm để nuôi nền cho những ngày nghỉ
                            # (Sửa lỗi: dùng total_off_days thay vì count_days['off'])
                            energy_td_used_for_off = total_off_days * 6 * p_base
                            kwh_td = max(0, kwh_td - energy_td_used_for_off)

                        # ===============================
                        # C. BÌNH THƯỜNG
                        # ===============================
                        # Sửa lỗi: Tách rõ nghỉ thường (13h) và nghỉ CN (18h)
                        total_base_kwh_bt = (
                            (count_days['off_weekday'] * 13 * p_base) +
                            (count_days['off_sunday'] * 18 * p_base) +
                            (count_days['week_work'] * 13 * p_base) +
                            (count_days['sun_work'] * 18 * p_base)
                        )

                        energy_fake_peak_sun = count_days['sun_work'] * hours_cd_in_shift * p_add_cd
                        prod_kwh_bt = max(0, kwh_bt - total_base_kwh_bt - energy_fake_peak_sun)

                        total_hours_bt_run = (
                            (count_days['week_work'] + count_days['sun_work']) * hours_bt_in_shift
                        )

                        p_add_bt = prod_kwh_bt / total_hours_bt_run if total_hours_bt_run > 0 else 0

                        # --- G. TẠO DATASET ---
                        def create_profile(mode):
                            data = {'td': [], 'bt_l': [], 'cd_l': [], 'bt_u': [], 'cd_u': []}
                            
                            is_off = 'off' in mode
                            is_sunday_mode = (mode == 'sun_work' or mode == 'off_sunday')
                            
                            for h in range(24):
                                is_machine_running = (not is_off) and (h_start <= h < real_h_end)
                                
                                p_machine = 0
                                if is_machine_running:
                                    if h in [22, 23, 0, 1, 2, 3]: p_machine = 0 
                                    elif h == 10 or h in [17, 18, 19]: p_machine = p_add_cd
                                    elif h == 9 or h == 11: p_machine = (p_add_cd + p_add_bt)/2
                                    else: p_machine = p_add_bt
                                
                                p_total = p_base + p_machine
                                v_td, v_bt_l, v_cd_l, v_bt_u, v_cd_u = 0, 0, 0, 0, 0
                                
                                # Phân màu
                                if h in [22, 23, 0, 1, 2, 3]: 
                                    v_td = p_base 
                                elif is_sunday_mode: # Giá CN (Full Xanh)
                                    v_bt_l = p_total
                                else: # Giá Ngày Thường (Có Đỏ)
                                    if h == 9: 
                                        v_bt_l = p_total * 0.5; v_cd_u = p_total * 0.5
                                    elif h == 11: 
                                        v_cd_l = p_total * 0.5; v_bt_u = p_total * 0.5
                                    elif h == 10 or h in [17, 18, 19]: 
                                        v_cd_l = p_total
                                    else: 
                                        v_bt_l = p_total
                                
                                data['td'].append(round(v_td, 2))
                                data['bt_l'].append(round(v_bt_l, 2))
                                data['cd_l'].append(round(v_cd_l, 2))
                                data['bt_u'].append(round(v_bt_u, 2))
                                data['cd_u'].append(round(v_cd_u, 2))
                            return data

                        du_lieu_nhap['chart_data'] = {
                            'labels': [f"{h}h" for h in range(24)],
                            'stats': {
                                'total': total_days, 
                                'work': count_days['week_work'] + count_days['sun_work'], 
                                'off': total_off_days,
                                'off_weekday_count': count_days['off_weekday'],
                                'off_sunday_count': count_days['off_sunday'],
                                'sun_work_count': count_days['sun_work']
                            },
                            'weekday_work': create_profile('week_work'),
                            'sunday_work': create_profile('sun_work'),
                            'off_weekday': create_profile('off_weekday'), 
                            'off_sunday': create_profile('off_sunday')
                        }

            except Exception as e: 
                print(f"Lỗi Backend: {e}") # In lỗi ra để kiểm tra
                msg_update = f"❌ Lỗi: {str(e)}"
            
            active_tab = 'calc' # Đảm bảo dòng này nằm ngoài except để luôn set active tab

    # --- 7. ĐỌC LỊCH SỬ GỘP (ĐỂ Ở NGOÀI CÙNG, CHẠY CHO CẢ GET VÀ POST) ---
    lich_su_data = []
    if os.path.exists(history_path):
        try:
            all_sheets = pd.read_excel(history_path, sheet_name=None)
            for s_name, df in all_sheets.items():
                if not df.empty:
                    df['id_row'] = df.index
                    df['sheet_source'] = s_name
                    lich_su_data.extend(df.to_dict('records'))
            lich_su_data.sort(key=lambda x: datetime.strptime(x['Thời Gian'], "%d/%m/%Y %H:%M:%S"), reverse=True)
        except: pass

    return render_template('index.html', role=current_role, settings=SETTINGS, users=USERS, ket_qua=ket_qua, dien_tich=dien_tich, du_lieu_nhap=du_lieu_nhap, msg_update=msg_update, active_tab=active_tab, gio_nang_da_dung=gio_nang_da_dung, lich_su=lich_su_data)


# --- ROUTE XÓA LỊCH SỬ ---
@app.route('/delete_history', methods=['POST'])
def delete_history():
    if 'user' not in session or session.get('role') != 'admin': return "Unauthorized", 403
    try:
        row_index = int(request.form.get('row_index'))
        sheet_source = request.form.get('sheet_source')
        
        if os.path.exists(history_path):
            all_sheets = pd.read_excel(history_path, sheet_name=None)
            if sheet_source in all_sheets:
                all_sheets[sheet_source] = all_sheets[sheet_source].drop(index=row_index)
                with pd.ExcelWriter(history_path) as writer:
                    for name, data in all_sheets.items(): data.to_excel(writer, sheet_name=name, index=False)
                    
        return redirect(url_for('home', active_tab='history'))
    except: return "Lỗi xóa"

# --- ROUTE TẢI FILE EXCEL ---
@app.route('/download_excel')
def download_excel():
    if 'user' not in session or session.get('role') != 'admin': return "Cấm!", 403
    if os.path.exists(history_path):
        return send_file(history_path, as_attachment=True, download_name='Lich_Su_Khach_Hang.xlsx')
    else: return "Chưa có file!", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=17005)