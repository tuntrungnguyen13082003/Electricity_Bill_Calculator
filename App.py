import os
import json
import requests
import base64
import re
import pandas as pd
from datetime import datetime, timedelta
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

# --- CÁC HÀM HỖ TRỢ (GIỮ NGUYÊN) ---
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def load_json_file(filepath, default_data):
    try:
        with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
    except: return default_data

def save_json_file(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

def load_excel_provinces():
    default_data = {"Hà Nội": 3.8, "TP. HCM": 4.5, "An Giang": 4.0}
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

def save_excel_provinces(dict_data):
    try:
        df = pd.DataFrame(list(dict_data.items()), columns=['Ten_Tinh', 'Gio_Nang'])
        df.to_excel(excel_path, index=False)
    except: pass

# --- AI ĐỌC HÓA ĐƠN (GIỮ NGUYÊN) ---
def ai_doc_hoa_don(image_path):
    print("--- Đang gửi yêu cầu tới Google AI (Qua REST API)... ---")
    
    # 1. Chuẩn bị dữ liệu gửi đi
    try:
        base64_image = encode_image(image_path)
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
        
        headers = {'Content-Type': 'application/json'}
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": """
                        Bạn là trợ lý nhập liệu. Hãy trích xuất dữ liệu từ hóa đơn điện này thành JSON.
                        Quy tắc:
                        1. Tìm cột 'ĐIỆN TIÊU THỤ (kWh)' để lấy số liệu.
                        2. Loại bỏ dấu chấm phân cách ngàn (Ví dụ: 19.619 -> 19619).
                        3. Ngày tháng chuyển về định dạng YYYY-MM-DD.
                        
                        Các trường cần lấy:
                        - kwh_bt (Bình thường)
                        - kwh_cd (Cao điểm)
                        - kwh_td (Thấp điểm)
                        - ngay_dau (Ngày bắt đầu)
                        - ngay_cuoi (Ngày kết thúc)
                        
                        Chỉ trả về đúng chuỗi JSON, không giải thích thêm.
                    """},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }]
        }

        # 2. Gửi yêu cầu (POST)
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        print(f"--- TRẠNG THÁI GỬI: {response.status_code} ---")
        if response.status_code != 200:
            print("--- NỘI DUNG LỖI TỪ GOOGLE: ---")
            print(response.text)

        # 3. Xử lý kết quả trả về
        if response.status_code == 200:
            result = response.json()
            # Lấy nội dung văn bản AI trả lời
            text_response = result['candidates'][0]['content']['parts'][0]['text']
            
            print("AI Trả lời:", text_response)
            
            # Dùng Regex để bắt lấy đoạn JSON
            match = re.search(r'\{.*\}', text_response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            else:
                print("Lỗi: Không tìm thấy JSON trong phản hồi.")
                return None
        else:
            print(f"Lỗi API: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"--- LỖI CODE PYTHON: {e}")
        return None

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

# --- DATA MẶC ĐỊNH ---
DEFAULT_SETTINGS = { 
    "evn_bac": [1806, 1866, 2167, 2729, 3050, 3151], 
    "gia_kinh_doanh": 2666, "gia_san_xuat": 1600, "tinh_thanh": {}, "dien_tich_kwp": 4.5,
    "he_so_nhom": { "gd_co_nguoi": 0.7, "gd_di_lam": 0.4, "gd_ban_dem": 0.3, "kd_min": 0.8, "kd_max": 0.9, "sx_min": 0.7, "sx_max": 0.8 }
}
DEFAULT_USERS = { "admin": {"password": "admin", "role": "admin"}, "user": {"password": "user", "role": "user"} }

# --- LOGIC TÍNH TOÁN ---
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

    def calc(hs):
        res = ((kWh * hs) / 30) / gio_nang_tinh
        return round(max(res, 1.0), 2)

    hs_data = settings.get('he_so_nhom', {})
    
    if loai_hinh == 'can_ho':
        # QUAN TRỌNG: Sử dụng he_so_form được truyền vào (từ dropdown)
        return [calc(he_so_form), calc(he_so_form)] 
    elif loai_hinh == 'kinh_doanh':
        return [calc(hs_data.get('kd_min', 0.2)), calc(hs_data.get('kd_max', 0.3))]
    elif loai_hinh == 'san_xuat':
        return [calc(hs_data.get('sx_min', 0.2)), calc(hs_data.get('sx_max', 0.3))]
    return [0, 0]

# --- ROUTE CHÍNH: TÍNH TOÁN & XỬ LÝ FORM ---
@app.route('/tinh_toan', methods=['POST'])
def xu_ly_tinh_toan():
    if 'user' not in session: return redirect(url_for('login'))
    
    # 1. LOAD DỮ LIỆU NỀN (Để render lại trang index không bị lỗi)
    current_role = session.get('role', 'user')
    SETTINGS = load_json_file(settings_path, DEFAULT_SETTINGS)
    SETTINGS['tinh_thanh'] = load_excel_provinces()
    USERS = load_json_file(users_path, DEFAULT_USERS)
    
    # Load lịch sử
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

    # 2. LẤY DỮ LIỆU INPUT
    ten_kh = request.form.get('ten_kh', '').strip()
    loai_hinh_raw = request.form.get('loai_hinh')
    loai_hinh = 'can_ho' if loai_hinh_raw == 'ho_gia_dinh' else loai_hinh_raw
    khu_vuc = request.form.get('khu_vuc')
    
    # Lấy hệ số thói quen (Fix lỗi mất hệ số)
    # Nếu form không gửi lên (trường hợp cũ), mặc định 0.5
    try:
        he_so_form = float(request.form.get('he_so_nhap') or 0.5)
    except:
        he_so_form = 0.5

    # Hàm lấy số an toàn (Tránh lỗi 500)
    def lay_so(key):
        raw = request.form.get(key, '0')
        if not raw: return 0.0
        return float(str(raw).replace('.', '').replace(',', ''))

    # Chuẩn bị biến du_lieu_nhap để trả về HTML (Giữ liệu cũ)
    du_lieu_nhap = {
        'ten_kh': ten_kh, 'loai_hinh': loai_hinh_raw, 'khu_vuc': khu_vuc,
        'he_so_nhap': he_so_form, # Trả lại hệ số để dropdown chọn đúng
        'kieu_nhap': request.form.get('kieu_nhap')
    }

    # CHECK TÊN KHÁCH HÀNG
    if not ten_kh:
        return render_template('index.html', role=current_role, settings=SETTINGS, users=USERS, lich_su=lich_su_data, 
                               active_tab='calc', msg_update="⚠️ Lỗi: Vui lòng nhập Tên Khách Hàng!", du_lieu_nhap=du_lieu_nhap)

    gia_tri_final = 0
    che_do_nhap = ''
    chart_data = None

    # 3. XỬ LÝ LOGIC THEO LOẠI HÌNH
    if loai_hinh in ['kinh_doanh', 'san_xuat']:
        k_bt = lay_so('kwh_bt')
        k_cd = lay_so('kwh_cd')
        k_td = lay_so('kwh_td')
        
        # Check tổng điện > 0
        if (k_bt + k_cd + k_td) <= 0:
             return render_template('index.html', role=current_role, settings=SETTINGS, users=USERS, lich_su=lich_su_data, 
                                    active_tab='calc', msg_update="⚠️ Lỗi: Vui lòng nhập ít nhất một chỉ số điện!", du_lieu_nhap=du_lieu_nhap)
        
        gia_tri_final = k_bt + k_cd + k_td
        che_do_nhap = 'theo_kwh'
        
        # Lưu lại input KD/SX
        du_lieu_nhap.update({
            'kwh_bt': k_bt, 'kwh_cd': k_cd, 'kwh_td': k_td,
            'ngay_dau': request.form.get('ngay_dau'), 'ngay_cuoi': request.form.get('ngay_cuoi'),
            'gio_lam_tu': request.form.get('gio_lam_tu'), 'gio_lam_den': request.form.get('gio_lam_den'),
            'list_ngay_nghi': [int(x) for x in request.form.getlist('ngay_nghi')]
        })
        
        # Logic vẽ biểu đồ (Placeholder)
        if request.form.get('co_ve_bieu_do') == 'yes':
            # Logic tính toán biểu đồ của bạn đặt ở đây
            # Tạm thời trả về dummy data để test giao diện
            chart_data = {'message': 'Đã phân tích biểu đồ thành công!', 'stats': {'total': 30, 'work': 26, 'off': 4}}
            du_lieu_nhap['chart_data'] = chart_data

    else: # Hộ gia đình
        kieu_nhap = request.form.get('kieu_nhap')
        val_nhap = lay_so('gia_tri_nhap')
        
        # Check số liệu > 0
        if val_nhap <= 0:
             return render_template('index.html', role=current_role, settings=SETTINGS, users=USERS, lich_su=lich_su_data, 
                                    active_tab='calc', msg_update="⚠️ Lỗi: Vui lòng nhập Số tiền hoặc Số điện!", du_lieu_nhap=du_lieu_nhap)
        
        gia_tri_final = val_nhap
        che_do_nhap = 'theo_kwh' if kieu_nhap == 'dien' else 'theo_tien'
        
        # Lưu lại input Hộ gia đình
        du_lieu_nhap['gia_tri_nhap'] = request.form.get('gia_tri_nhap') # Giữ nguyên format có dấu chấm

    # 4. TÍNH TOÁN CÔNG SUẤT
    gio_nang = SETTINGS['tinh_thanh'].get(khu_vuc, 4.0)
    ket_qua = tinh_toan_kwp(loai_hinh, gia_tri_final, che_do_nhap, he_so_form, gio_nang, SETTINGS)
    
    # Format kết quả hiển thị
    kwp_min, kwp_max = ket_qua[0], ket_qua[1]
    he_so_dt = SETTINGS.get('dien_tich_kwp', 4.5)
    
    str_ket_qua = f"{kwp_min}" if kwp_min == kwp_max else f"{kwp_min} - {kwp_max}"
    str_dien_tich = f"≈ {round(kwp_min * he_so_dt, 1)}" if kwp_min == kwp_max else f"{round(kwp_min * he_so_dt, 1)} - {round(kwp_max * he_so_dt, 1)}"
    
    excel_res = f"{str_ket_qua} kWp (≈{str_dien_tich} m²)"

    # 5. LƯU LỊCH SỬ EXCEL
    try:
        map_sheet = {'can_ho': 'Hộ Gia Đình', 'kinh_doanh': 'Kinh Doanh', 'san_xuat': 'Sản Xuất'}
        ten_sheet = map_sheet.get(loai_hinh, 'Khác')
        thoi_gian = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        don_vi = 'VNĐ' if che_do_nhap == 'theo_tien' else 'kWh'
        str_dau_vao = f"{gia_tri_final:,.0f} {don_vi}".replace(',', '.')
        
        new_row = pd.DataFrame([{
            "Tên Khách Hàng": ten_kh, "Thời Gian": thoi_gian, 
            "Khu Vực": f"{khu_vuc}", "Đầu Vào": str_dau_vao, 
            "Kết Quả (kWp)": excel_res
        }])
        
        all_sheets = pd.read_excel(history_path, sheet_name=None) if os.path.exists(history_path) else {}
        if ten_sheet in all_sheets: all_sheets[ten_sheet] = pd.concat([all_sheets[ten_sheet], new_row], ignore_index=True)
        else: all_sheets[ten_sheet] = new_row
        
        with pd.ExcelWriter(history_path) as writer:
            for s_name, data in all_sheets.items(): data.to_excel(writer, sheet_name=s_name, index=False)
            
        lich_su_data.insert(0, new_row.to_dict('records')[0])
    except Exception as e:
        print(f"Lỗi lưu file: {e}")

    # 6. TRẢ VỀ GIAO DIỆN
    return render_template('index.html', 
                           role=current_role, settings=SETTINGS, users=USERS, lich_su=lich_su_data,
                           ket_qua=str_ket_qua, dien_tich=str_dien_tich, 
                           du_lieu_nhap=du_lieu_nhap, active_tab='calc',
                           msg_update="✅ Tính toán thành công!")

# --- CÁC ROUTE CÒN LẠI (LOGIN, HOME, CONFIG...) ---
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
    
    msg_update = None
    active_tab = request.args.get('active_tab', 'calc')
    du_lieu_nhap = {}

    # XỬ LÝ POST (Cấu hình, User, Đổi pass...)
    if request.method == 'POST':
        if 'btn_change_pass' in request.form:
            op, np = request.form.get('old_pass'), request.form.get('new_pass')
            if USERS[current_user]['password'] == op:
                USERS[current_user]['password'] = np; save_json_file(users_path, USERS)
                msg_update = "✅ Đổi pass thành công!"; active_tab = 'account'
            else: msg_update = "❌ Pass cũ sai!"; active_tab = 'account'

        elif 'btn_add_user' in request.form and current_role == 'admin':
            nu, np, nr = request.form.get('new_username'), request.form.get('new_password'), request.form.get('new_role')
            if nu and np:
                USERS[nu] = {"password": np, "role": nr}; save_json_file(users_path, USERS); msg_update = f"✅ Tạo {nu} xong!"
            active_tab = 'users'
        
        elif 'btn_delete_user' in request.form and current_role == 'admin':
            del_u = request.form.get('btn_delete_user')
            if del_u not in ['admin', current_user]: del USERS[del_u]; save_json_file(users_path, USERS)
            active_tab = 'users'

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
                    raw = get_float(f'hs_{k}')
                    SETTINGS['he_so_nhom'][k] = min(1.0, max(0.0, raw))
                    
                save_json_file(settings_path, {k:v for k,v in SETTINGS.items() if k != 'tinh_thanh'})
                msg_update = "✅ Đã lưu giá!"; active_tab = 'config'
            except: msg_update = "❌ Lỗi nhập số!"; active_tab = 'config'
        
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

    # Load lịch sử
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

    return render_template('index.html', role=current_role, settings=SETTINGS, users=USERS, 
                           msg_update=msg_update, active_tab=active_tab, lich_su=lich_su_data, du_lieu_nhap=du_lieu_nhap)

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

@app.route('/download_excel')
def download_excel():
    if 'user' not in session or session.get('role') != 'admin': return "Cấm!", 403
    if os.path.exists(history_path):
        return send_file(history_path, as_attachment=True, download_name='Lich_Su_Khach_Hang.xlsx')
    else: return "Chưa có file!", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=17005, debug=True)