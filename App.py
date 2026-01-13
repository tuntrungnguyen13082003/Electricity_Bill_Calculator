import os
import json
import requests
import pytz
import base64
import re
import pdfplumber
import pandas as pd
from datetime import datetime, timedelta # Thêm timedelta
from datetime import datetime
from flask import Flask, jsonify, render_template, request, session, redirect, url_for, send_file

API_KEY = "AIzaSyAkDousFLZy33pXCo3by3zZ8ar3Pphuy0c"

# --- CẤU HÌNH ---
base_dir = os.path.abspath(os.path.dirname(__file__))
settings_path = os.path.join(base_dir, 'data', 'settings.json')
users_path = os.path.join(base_dir, 'data', 'users.json')
excel_path = os.path.join(base_dir, 'data', 'tinh_thanh.xlsx')
history_path = os.path.join(base_dir, 'data', 'lich_su_khach_hang.xlsx')
template_path = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_path)
app.secret_key = 'khoa_bi_mat_cua_du_an_solar'

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')
    
# --- HÀM ĐỌC HÓA ĐƠN (PHIÊN BẢN SIÊU TƯƠNG THÍCH - ĐÃ CẬP NHẬT) ---
def ai_doc_hoa_don(file_path):
    # Chỉ xử lý nếu là file PDF
    if not file_path.lower().endswith('.pdf'):
        print("Lỗi: Thư viện này chỉ hỗ trợ file PDF gốc.")
        return None

    # Khởi tạo dữ liệu mặc định
    data = {
        "loai_hinh": "can_ho", # Mặc định là hộ gia đình
        "kwh_tong": 0,         # Dành cho hộ gia đình
        "kwh_bt": 0,           # Dành cho KD/SX
        "kwh_cd": 0,           # Dành cho KD/SX
        "kwh_td": 0,           # Dành cho KD/SX
        "ngay_dau": "",
        "ngay_cuoi": ""
    }

    try:
        with pdfplumber.open(file_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

            # --- 1. NHẬN DIỆN MÔ HÌNH LẮP ĐẶT ---
            # Nếu thấy từ khóa về khung giờ thì chuyển sang mô hình kinh doanh
            if any(x in full_text for x in ["Khung giờ", "BT:", "CD:", "TD:"]):
                data["loai_hinh"] = "kinh_doanh"
            else:
                data["loai_hinh"] = "can_ho"

            # --- 2. TRÍCH XUẤT NGÀY THÁNG (Giữ nguyên của bạn) ---
            date_match = re.search(r"từ\s+(\d{2}/\d{2}/\d{4})\s+đến\s+(\d{2}/\d{2}/\d{4})", full_text)
            if date_match:
                d1 = datetime.strptime(date_match.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
                d2 = datetime.strptime(date_match.group(2), "%d/%m/%Y").strftime("%Y-%m-%d")
                data["ngay_dau"] = d1
                data["ngay_cuoi"] = d2

            # --- 3. TRÍCH XUẤT SẢN LƯỢNG (KWH) ---
            if data["loai_hinh"] == "can_ho":
                # Ưu tiên tìm dòng Tổng điện năng tiêu thụ (kWh) có trong hóa đơn sinh hoạt 
                tong_match = re.search(r"Tổng điện năng tiêu thụ \(kWh\).*?([\d\.,]+)", full_text, re.IGNORECASE)
                if not tong_match:
                    # Nếu không thấy, tìm dòng "Toàn thời gian" (thường chứa tổng sản lượng hộ gia đình) [cite: 10, 50]
                    tong_match = re.search(r"Toàn thời gian.*?([\d\.,]+)\s+[\d\.,]+$", full_text, re.MULTILINE)
                
                if tong_match:
                    val = tong_match.group(1).replace('.', '').replace(',', '.')
                    data["kwh_tong"] = float(val)
            else:
                # --- NHÁNH KINH DOANH / SẢN XUẤT ---
                # Sử dụng Regex linh hoạt hơn để bắt được số ở giữa Đơn giá và Thành tiền
                # Mẫu: [Tên khung giờ] [Đơn giá] [Sản lượng cần lấy] [Thành tiền]
                
                def extract_biz_kwh(pattern_str):
                    # Tìm dòng chứa từ khóa, lấy con số nằm ở cột Sản lượng (thường là số thứ 2 hoặc số gần cuối)
                    match = re.search(pattern_str + r".*?[\d\.,]+\s+([\d\.,]+)\s+[\d\.,]+", full_text, re.IGNORECASE | re.MULTILINE)
                    if not match:
                        # Backup: Tìm theo cách cũ nếu định dạng text bị trôi dòng
                        match = re.search(pattern_str + r".*?([\d\.,]+)$", full_text, re.IGNORECASE | re.MULTILINE)
                    return float(match.group(1).replace('.', '').replace(',', '.')) if match else 0

                data["kwh_bt"] = extract_biz_kwh("Bình thường")
                data["kwh_cd"] = extract_biz_kwh("Cao điểm")
                data["kwh_td"] = extract_biz_kwh("Thấp điểm")
                
                # Nếu tất cả bằng 0, thử tìm theo từ viết tắt (BT, CD, TD)
                if data["kwh_bt"] == 0 and data["kwh_cd"] == 0:
                    data["kwh_bt"] = extract_biz_kwh("BT")
                    data["kwh_cd"] = extract_biz_kwh("CD")
                    data["kwh_td"] = extract_biz_kwh("TD")

        return data

    except Exception as e:
        print(f"Lỗi trích xuất PDF trực tiếp: {e}")
        return None
    
# --- 3. TẠO ĐƯỜNG DẪN (ROUTE) ĐỂ WEB GỌI ---
@app.route('/scan_invoice', methods=['POST'])
def scan_invoice():
    if 'file_anh' not in request.files:
        return jsonify({'success': False, 'error': 'Không có file'}), 400
    
    file = request.files['file_anh']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Chưa chọn file'}), 400

    if file:
        # Lưu tạm ảnh
        if not os.path.exists("uploads"): os.makedirs("uploads")
        temp_path = os.path.join("uploads", file.filename)
        file.save(temp_path)
        
        # Gọi AI xử lý
        data = ai_doc_hoa_don(temp_path)
        
        # Xóa ảnh sau khi xong
        if os.path.exists(temp_path): os.remove(temp_path)
        
        if data:
            return jsonify({'success': True, 'data': data})
        else:
            return jsonify({'success': False, 'error': 'AI không đọc được dữ liệu'}), 500

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
        # 1. ĐỔI PASS (Giữ nguyên)
        if 'btn_change_pass' in request.form:
            op, np = request.form.get('old_pass'), request.form.get('new_pass')
            if USERS[current_user]['password'] == op:
                USERS[current_user]['password'] = np; save_json_file(users_path, USERS)
                msg_update = "✅ Đổi pass thành công!"
            else: msg_update = "❌ Pass cũ sai!"
            active_tab = 'account'

        # 2. QUẢN LÝ USER (Giữ nguyên)
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

        # 3. CẬP NHẬT GIÁ (Giữ nguyên)
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
                for k in ['gd_co_nguoi', 'gd_di_lam', 'gd_ban_dem', 'kd_min', 'kd_max', 'sx_min', 'sx_max']:
                    SETTINGS['he_so_nhom'][k] = min(1.0, max(0.0, get_float(f'hs_{k}')))
                save_json_file(settings_path, {k:v for k,v in SETTINGS.items() if k != 'tinh_thanh'})
                msg_update = "✅ Đã lưu giá!"
            except: msg_update = "❌ Lỗi nhập số!"
            active_tab = 'config'

        # 4. QUẢN LÝ TỈNH (Giữ nguyên)
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

        # 5. XỬ LÝ TÍNH TOÁN HỢP NHẤT (THUẬT TOÁN MỚI: ƯU TIÊN TẢI NỀN)
        elif 'btn_calc' in request.form:
            try:
                # --- A. CẬP NHẬT DỮ LIỆU FORM (GIỮ NGUYÊN) ---
                ten_kh = request.form.get('ten_khach_hang', 'Khách vãng lai')
                lh, tc = request.form.get('loai_hinh'), request.form.get('tinh_thanh_chon')
                gn = SETTINGS['tinh_thanh'].get(tc, 4.0)
                he_so_dt = SETTINGS.get('dien_tich_kwp', 4.5)
                du_lieu_nhap.update({'ten_kh': ten_kh, 'loai_hinh': lh, 'tinh_chon': tc})

                if lh == 'can_ho':
                    # =================================================
                    # 1. LOGIC HỘ GIA ĐÌNH (CHỈ DÙNG SỐ ĐIỆN kWh)
                    # =================================================
                    # Bước 1: Lấy dữ liệu từ Form
                    raw_gt = request.form.get('gia_tri_dau_vao', '0')
                    # HGD giờ chỉ dùng kWh, 'theo_kwh' được lấy từ input hidden hoặc ép cứng tại đây
                    cd = 'theo_kwh' 
                    
                    # Xử lý chuỗi số (xóa dấu chấm/phẩy) để tính toán
                    val_str = raw_gt.replace('.', '').replace(',', '')
                    gt = float(val_str) if val_str else 0
                    
                    hs = float(request.form.get('he_so_nhap') or 0.5)
                    ngu_canh = request.form.get('ngu_canh_chon')

                    # Bước 2: Cập nhật dữ liệu nhập để hiển thị lại trên Web
                    du_lieu_nhap.update({
                        'gia_tri': raw_gt,
                        'che_do': cd, 
                        'he_so': hs, 
                        'ngu_canh': ngu_canh
                    })

                    # Bước 3: Tính toán kWp (Giữ nguyên logic kiểm tra hàm sẵn có)
                    if 'tinh_toan_kwp' in globals():
                        kwp_list = tinh_toan_kwp(lh, gt, cd, hs, gn, SETTINGS)
                        kwp_min, kwp_max = kwp_list[0], kwp_list[1]
                    else:
                        # Fallback tính toán đơn giản nếu không tìm thấy hàm
                        uoc_luong = gt / 30 / gn if gn > 0 else 0
                        kwp_min = round(uoc_luong, 2)
                        kwp_max = round(uoc_luong, 2)

                    # Bước 4: Định dạng chuỗi để lưu vào Excel (Theo yêu cầu mới)
                    # - Đầu vào: Luôn hiển thị đơn vị kWh
                    gia_tri_dau_vao_kem_dv = f"{raw_gt} kWh"
                    
                    # - Kết quả: Hiện 1 con số kWp duy nhất và diện tích mái
                    dt_uoc_tinh = round(kwp_min * he_so_dt, 1)
                    ket_qua_kem_dt = f"{kwp_min} kWp (Mái: {dt_uoc_tinh} m²)"

                else:
                    # --- B. NHÁNH KINH DOANH / SẢN XUẤT (THUẬT TOÁN MỚI) ---
                    # Bước 1: Lấy dữ liệu input
                    def get_hour_safe(key, default_h):
                        val = request.form.get(key, "")
                        if not val: return default_h
                        try:
                            parts = val.strip().split(' ')
                            h = int(parts[0].split(':')[0])
                            if len(parts) > 1:
                                suffix = parts[1].upper()
                                if ('CH' in suffix or 'PM' in suffix) and h < 12: h += 12
                                if ('SA' in suffix or 'AM' in suffix) and h == 12: h = 0
                            return h
                        except: return default_h

                    # 2. Lấy Input
                    kwh_cd = float(request.form.get('kwh_cd') or 0)
                    kwh_td = float(request.form.get('kwh_td') or 0)
                    kwh_bt = float(request.form.get('kwh_bt') or 0)
                    d_start, d_end = request.form.get('ngay_dau'), request.form.get('ngay_cuoi')
                    h_start = get_hour_safe('gio_lam_tu', 8)
                    h_end = get_hour_safe('gio_lam_den', 17)
                    list_ngay_nghi = [int(x) for x in request.form.getlist('ngay_nghi')]

                    du_lieu_nhap.update({
                        'kwh_cd': kwh_cd, 'kwh_td': kwh_td, 'kwh_bt': kwh_bt,
                        'ngay_dau': d_start, 'ngay_cuoi': d_end,
                        'gio_lam_tu': request.form.get('gio_lam_tu'), 
                        'gio_lam_den': request.form.get('gio_lam_den'),
                        'list_ngay_nghi': list_ngay_nghi
                    })

                    # Bước 2: Tính toán kWp dải Min - Max
                    pref = 'kd' if lh == 'kinh_doanh' else 'sx'
                    hs_min, hs_max = SETTINGS['he_so_nhom'].get(f'{pref}_min', 0.1), SETTINGS['he_so_nhom'].get(f'{pref}_max', 0.25)
                    total_kwh = kwh_bt + kwh_cd + kwh_td
                    kwp_min = round(((total_kwh * hs_min) / 30) / gn, 2)
                    kwp_max = round(((total_kwh * hs_max) / 30) / gn, 2)

                    # Bước 3: Định dạng chuỗi lưu Excel cho Kinh doanh / Sản xuất
                    gia_tri_dau_vao_kem_dv = f"{total_kwh} kWh"
                    dt_min = round(kwp_min * he_so_dt, 1)
                    dt_max = round(kwp_max * he_so_dt, 1)
                    ket_qua_kem_dt = f"{kwp_min} ➔ {kwp_max} kWp (Mái: {dt_min} ➔ {dt_max} m²)"

                    # --- C. THUẬT TOÁN PHÂN TÍCH BIỂU ĐỒ (CORE MỚI) ---
                    if request.form.get('co_ve_bieu_do') == 'yes' and d_start and d_end:
                        start_date = datetime.strptime(d_start, "%Y-%m-%d")
                        end_date = datetime.strptime(d_end, "%Y-%m-%d")
                        total_days = (end_date - start_date).days + 1
                        
                        if total_days > 0:
                            # 1. Đếm số ngày
                            count_days = {'total': total_days, 'week_work': 0, 'sun_work': 0, 'off_weekday': 0, 'off_sunday': 0}
                            for i in range(total_days):
                                curr = start_date + timedelta(days=i)
                                wd = curr.weekday()
                                if wd in list_ngay_nghi:
                                    if wd == 6: count_days['off_sunday'] += 1
                                    else: count_days['off_weekday'] += 1
                                else:
                                    if wd == 6: count_days['sun_work'] += 1
                                    else: count_days['week_work'] += 1

                            # 2. Tính Tải Nền (P_base) từ Thấp điểm
                            # Ý tưởng: Thấp điểm nuôi nền cho TOÀN BỘ các ngày
                            p_base = (kwh_td / total_days) / 6 if kwh_td > 0 else 0

                            # 3. Phân tích giờ trong ca làm việc
                            hours_cd_in_shift = 0; hours_bt_in_shift = 0
                            real_h_end = max(h_start + 1, h_end)
                            for h in range(h_start, real_h_end):
                                if h in [22, 23, 0, 1, 2, 3]: pass 
                                elif h == 10 or h in [17, 18, 19]: hours_cd_in_shift += 1
                                elif h == 9 or h == 11: hours_cd_in_shift += 0.5; hours_bt_in_shift += 0.5
                                else: hours_bt_in_shift += 1

                            # ====================================================
                            # 4. TÍNH CÔNG SUẤT MÁY (P_ADD) - THEO YÊU CẦU MỚI
                            # ====================================================
                            
                            # --- Bước 4.1: Xử lý CAO ĐIỂM (kwh_cd) ---
                            # Trừ đi lượng điện tải nền ăn trong giờ cao điểm của TẤT CẢ các ngày (nghỉ + làm)
                            # EVN tính cao điểm cho cả Thứ 2 -> Thứ 7 (kể cả ngày nghỉ)
                            total_hours_cd_base_weekday = (count_days['week_work'] + count_days['off_weekday']) * 5 # 5h cao điểm/ngày
                            energy_cd_for_base = total_hours_cd_base_weekday * p_base
                            
                            rem_kwh_cd = max(0, kwh_cd - energy_cd_for_base)

                            # Chia đều số điện còn lại cho giờ máy chạy của các ngày làm việc (trừ CN)
                            total_hours_machine_cd = count_days['week_work'] * hours_cd_in_shift
                            p_add_cd = rem_kwh_cd / total_hours_machine_cd if total_hours_machine_cd > 0 else 0

                            # --- Bước 4.2: Xử lý BÌNH THƯỜNG (kwh_bt) ---
                            # Trừ đi tải nền bình thường cho TẤT CẢ các ngày
                            # Ngày thường: 13h BT. Chủ nhật: 18h BT (vì 5h cao điểm biến thành BT)
                            total_hours_bt_base = (
                                (count_days['week_work'] + count_days['off_weekday']) * 13 + 
                                (count_days['sun_work'] + count_days['off_sunday']) * 18
                            )
                            energy_bt_for_base = total_hours_bt_base * p_base
                            
                            # ĐIỂM NHẤN: Đắp vào Chủ Nhật làm việc (9h30-11h30...)
                            # Lấy năng lượng Bình thường để chạy máy với công suất Cao điểm vào CN
                            energy_sun_fake_peak = count_days['sun_work'] * hours_cd_in_shift * p_add_cd
                            
                            rem_kwh_bt = max(0, kwh_bt - energy_bt_for_base - energy_sun_fake_peak)

                            # Chia đều phần còn lại cho giờ máy chạy bình thường
                            total_hours_machine_bt = (count_days['week_work'] + count_days['sun_work']) * hours_bt_in_shift
                            p_add_bt = rem_kwh_bt / total_hours_machine_bt if total_hours_machine_bt > 0 else 0

                            # 5. Tạo Profile 48 điểm
                            def create_profile(mode):
                                data = {'td': [], 'bt_l': [], 'cd_l': [], 'bt_u': [], 'cd_u': []}
                                is_off = 'off' in mode
                                is_sunday_mode = (mode == 'sun_work' or mode == 'off_sunday')
                                
                                for i in range(48):
                                    cur_h = i / 2
                                    # Kiểm tra giờ máy chạy
                                    is_running = (not is_off) and (h_start <= cur_h < real_h_end)
                                    
                                    p_machine = 0
                                    if is_running:
                                        # Nếu là giờ cao điểm (hoặc giờ giả cao điểm vào CN)
                                        if i in [19, 20, 21, 22] or i in range(34, 40):
                                            p_machine = p_add_cd # Luôn chạy công suất lớn
                                        else:
                                            p_machine = p_add_bt
                                    
                                    p_tot = p_base + p_machine
                                    
                                    # Phân loại màu sắc (Binning)
                                    v_td, v_bt, v_cd = 0, 0, 0
                                    if i >= 44 or i < 8: # Thấp điểm
                                        v_td = p_tot
                                    elif is_sunday_mode: # Chủ nhật (Toàn bộ còn lại là BT)
                                        v_bt = p_tot
                                    else: # Ngày thường (Có cao điểm)
                                        if i in [19, 20, 21, 22] or i in range(34, 40):
                                            v_cd = p_tot
                                        else:
                                            v_bt = p_tot
                                            
                                    data['td'].append(round(v_td, 2))
                                    data['bt_l'].append(round(v_bt, 2))
                                    data['cd_l'].append(round(v_cd, 2))
                                    # Giữ lại 2 mảng này (dù = 0) để tương thích cấu trúc cũ
                                    data['bt_u'].append(0); data['cd_u'].append(0)
                                return data

                            # 6. Đóng gói dữ liệu gửi xuống Frontend (BẢN FIX LỖI "NO ATTRIBUTE OFF")
                            du_lieu_nhap['chart_data'] = {
                                'labels': [f"{i//2}:{'30' if i%2!=0 else '00'}" for i in range(48)],
                                'stats': {
                                    'total': total_days, 
                                    # --- THÊM DÒNG NÀY ĐỂ SỬA LỖI ---
                                    'off': count_days['off_weekday'] + count_days['off_sunday'], 
                                    # --------------------------------
                                    'off_weekday_count': count_days['off_weekday'],
                                    'off_sunday_count': count_days['off_sunday']
                                },
                                'weekday_work': create_profile('week_work'), 
                                'sunday_work': create_profile('sun_work'),
                                'off_weekday': create_profile('off_weekday'), 
                                'off_sunday': create_profile('off_sunday')
                            }

                # Chuẩn bị kết quả hiển thị
                ket_qua = f"{kwp_min}" if kwp_min == kwp_max else f"{kwp_min} ➔ {kwp_max}"
                dien_tich = f"≈ {round(kwp_min * he_so_dt, 1)}" if kwp_min == kwp_max else f"{round(kwp_min * he_so_dt, 1)} ➔ {round(kwp_max * he_so_dt, 1)}"
                
                # Lưu Excel
                try:
                    map_sheet = {'can_ho': 'Hộ Gia Đình', 'kinh_doanh': 'Kinh Doanh', 'san_xuat': 'Sản Xuất'}
                    ten_sheet = map_sheet.get(lh, 'Khác')
                    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                    thoi_gian = datetime.now(vn_tz).strftime("%d/%m/%Y %H:%M:%S")
                    new_row = pd.DataFrame([{
                                "Thời Gian": thoi_gian,
                                "Tên Khách Hàng": ten_kh, 
                                "Khu Vực": tc, 
                                "Đầu Vào": gia_tri_dau_vao_kem_dv, 
                                "Kết Quả (kWp)": ket_qua_kem_dt
                            }])
                    
                    if os.path.exists(history_path):
                        all_sheets = pd.read_excel(history_path, sheet_name=None)
                    else:
                        all_sheets = {}
                        
                    if ten_sheet in all_sheets:
                        all_sheets[ten_sheet] = pd.concat([all_sheets[ten_sheet], new_row], ignore_index=True)
                    else:
                        all_sheets[ten_sheet] = new_row
                        
                    with pd.ExcelWriter(history_path) as writer:
                        for s_name, data in all_sheets.items():
                            data.to_excel(writer, sheet_name=s_name, index=False)
                except Exception as e: print(f"Lỗi Excel: {e}")

                active_tab = 'calc'
            except Exception as e:
                msg_update = f"❌ Lỗi: {str(e)}"

    # --- 6. ĐỌC LỊCH SỬ GỘP (ĐỂ Ở NGOÀI CÙNG, CHẠY CHO CẢ GET VÀ POST) ---
    lich_su_data = []
    if os.path.exists(history_path):
        try:
            all_sheets = pd.read_excel(history_path, sheet_name=None)
            for s_name, df in all_sheets.items():
                if not df.empty:
                    df = df.fillna('')
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