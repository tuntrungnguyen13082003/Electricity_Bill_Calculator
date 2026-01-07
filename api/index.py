import os
import json
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for
from openpyxl import load_workbook

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
    """Đọc file Excel, tự động lọc dòng trống và sửa lỗi dấu phẩy"""
    default_data = {"Hà Nội": 3.8, "TP. HCM": 4.5}
    try:
        df = pd.read_excel(excel_path)
        df.columns = df.columns.str.strip()
        
        if 'Ten_Tinh' not in df.columns or 'Gio_Nang' not in df.columns:
            return default_data

        df = df.dropna(subset=['Ten_Tinh', 'Gio_Nang'])

        # Sửa lỗi dấu phẩy (4,9 -> 4.9)
        df['Gio_Nang'] = df['Gio_Nang'].astype(str).str.replace(',', '.', regex=False)
        df['Gio_Nang'] = pd.to_numeric(df['Gio_Nang'], errors='coerce') 
        
        df = df.dropna(subset=['Gio_Nang'])
        return pd.Series(df.Gio_Nang.values, index=df.Ten_Tinh).to_dict()

    except Exception as e:
        print(f"Lỗi đọc Excel: {e}")
        return default_data

# --- HÀM XỬ LÝ EXCEL (GHI) ---
def save_excel_provinces(dict_data):
    """Lưu dữ liệu Dictionary vào file Excel"""
    try:
        # Chuyển Dictionary thành DataFrame
        df = pd.DataFrame(list(dict_data.items()), columns=['Ten_Tinh', 'Gio_Nang'])
        # Ghi đè vào file Excel
        df.to_excel(excel_path, index=False)
    except Exception as e:
        print(f"Lỗi ghi Excel: {e}")

# --- HÀM XỬ LÝ JSON ---
def load_json_file(filepath, default_data):
    try:
        with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
    except: return default_data

def save_json_file(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"Lỗi lưu JSON: {e}")

# Dữ liệu mặc định
DEFAULT_SETTINGS = { "evn_bac": [1806, 1866, 2167, 2729, 3050, 3151], "gia_kinh_doanh": 2666, "gia_san_xuat": 1600, "tinh_thanh": {},
                    "he_so_nhom": {  
                                    "gd_co_nguoi": 0.2,   
                                    "gd_di_lam": 0.15,     
                                    "gd_ban_dem": 0.15,    
                                    "kinh_doanh": 0.25,    
                                    "san_xuat": 0.25       
                                   }}
DEFAULT_USERS = { "admin": {"password": "admin", "role": "admin"}, "user": {"password": "user", "role": "user"} }

# --- HÀM TÍNH TOÁN ---
def tinh_nguoc_kwh_evn(tong_tien, settings):
    VAT = 1.08
    gia_bac = settings['evn_bac']
    bac_thang = [(50, gia_bac[0]*VAT), (50, gia_bac[1]*VAT), (100, gia_bac[2]*VAT), (100, gia_bac[3]*VAT), (100, gia_bac[4]*VAT), (float('inf'), gia_bac[5]*VAT)]
    kwh, tien = 0, tong_tien
    for so_kwh, don_gia in bac_thang:
        tien_max = so_kwh * don_gia
        if tien > tien_max: kwh += so_kwh; tien -= tien_max
        else: kwh += tien / don_gia; break
    return kwh

def tinh_toan_kwp(loai_hinh, gia_tri_nhap, che_do_nhap, he_so_nhap, gio_nang_tinh, settings):
    kWh = 0
    if che_do_nhap == 'theo_kwh': kWh = gia_tri_nhap
    else:
        tien_dien = gia_tri_nhap
        if loai_hinh == 'can_ho': kWh = tinh_nguoc_kwh_evn(tien_dien, settings)
        elif loai_hinh == 'kinh_doanh': kWh = tien_dien / settings['gia_kinh_doanh']
        elif loai_hinh == 'san_xuat': kWh = tien_dien / settings['gia_san_xuat']
    
    kwp_result = 0
    if kWh > 0 and gio_nang_tinh > 0:
        kwp_result = ((kWh * he_so_nhap) / 30) / gio_nang_tinh
    else: return 0
        
    if kwp_result < 1.0: kwp_result = 1.0
    elif kwp_result > 100.0: kwp_result = 100.0
    return round(kwp_result, 2)

# --- ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        USERS = load_json_file(users_path, DEFAULT_USERS)
        if user in USERS and USERS[user]['password'] == pwd:
            session['user'] = user
            session['role'] = USERS[user]['role']
            return redirect(url_for('home'))
        else: error = "Sai tài khoản hoặc mật khẩu!"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user' not in session: return redirect(url_for('login'))
    
    current_user = session['user']
    current_role = session.get('role', 'user')
    
    # LOAD DATA
    SETTINGS = load_json_file(settings_path, DEFAULT_SETTINGS)
    SETTINGS['tinh_thanh'] = load_excel_provinces() # Đọc từ Excel
    USERS = load_json_file(users_path, DEFAULT_USERS)

    ket_qua, msg_update = None, None
    active_tab = request.args.get('active_tab', 'calc')
    du_lieu_nhap = {'loai_hinh': 'can_ho', 'gia_tri': '', 'che_do': 'theo_tien', 'he_so': 0.5, 'tinh_chon': ''}
    gio_nang_da_dung = 0

    if request.method == 'POST':
        # 1. ĐỔI PASS
        if 'btn_change_pass' in request.form:
            op, np = request.form.get('old_pass'), request.form.get('new_pass')
            if USERS[current_user]['password'] == op:
                if np: USERS[current_user]['password'] = np; save_json_file(users_path, USERS); msg_update = "✅ Đổi pass thành công!"
                else: msg_update = "❌ Pass trống!"
            else: msg_update = "❌ Pass cũ sai!"
            active_tab = 'account'

        # 2. TẠO USER
        elif 'btn_add_user' in request.form and current_role == 'admin':
            nu, np, nr = request.form.get('new_username'), request.form.get('new_password'), request.form.get('new_role')
            if nu and np:
                if nu in USERS: msg_update = "❌ Tên trùng!"
                else: USERS[nu] = {"password": np, "role": nr}; save_json_file(users_path, USERS); msg_update = f"✅ Tạo {nu} xong!"
            active_tab = 'users'

        # 3. XÓA USER
        elif 'btn_delete_user' in request.form and current_role == 'admin':
            del_u = request.form.get('btn_delete_user')
            if del_u not in ['admin', current_user]: del USERS[del_u]; save_json_file(users_path, USERS); msg_update = f"🗑️ Đã xóa {del_u}"
            active_tab = 'users'

        # 4. CẬP NHẬT GIÁ
        elif 'btn_update_price' in request.form and current_role == 'admin':
            try:
                SETTINGS['evn_bac'] = [float(request.form.get(f'b{i}')) for i in range(1, 7)]
                SETTINGS['gia_kinh_doanh'] = float(request.form.get('gia_kd'))
                SETTINGS['gia_san_xuat'] = float(request.form.get('gia_sx'))
                
                if 'he_so_nhom' not in SETTINGS: SETTINGS['he_so_nhom'] = {}
                SETTINGS['he_so_nhom']['gd_co_nguoi'] = float(request.form.get('hs_gd_co_nguoi'))
                SETTINGS['he_so_nhom']['gd_di_lam'] = float(request.form.get('hs_gd_di_lam'))
                SETTINGS['he_so_nhom']['gd_ban_dem'] = float(request.form.get('hs_gd_ban_dem'))
                SETTINGS['he_so_nhom']['kinh_doanh'] = float(request.form.get('hs_kinh_doanh'))
                SETTINGS['he_so_nhom']['san_xuat'] = float(request.form.get('hs_san_xuat'))
                
                save_json_file(settings_path, {k:v for k,v in SETTINGS.items() if k != 'tinh_thanh'})
                msg_update = "✅ Đã lưu giá!"
            except: msg_update = "❌ Lỗi nhập số!"
            active_tab = 'config'

        # 5. THÊM TỈNH
        elif 'btn_add_province' in request.form and current_role == 'admin':
            t, h = request.form.get('new_province_name'), request.form.get('new_province_hours')
            try:
                if t and float(h) > 0:
                    SETTINGS['tinh_thanh'][t] = float(h)
                    save_excel_provinces(SETTINGS['tinh_thanh'])
                    msg_update = f"✅ Đã thêm {t} vào Excel!"
            except: pass
            active_tab = 'config'

        # 6. LƯU/XÓA TỈNH
        elif 'btn_save_list' in request.form and current_role == 'admin':
            updated = False
            for t in list(SETTINGS['tinh_thanh'].keys()):
                v = request.form.get(f"hours_{t}")
                if v and float(v) != SETTINGS['tinh_thanh'][t]:
                    SETTINGS['tinh_thanh'][t] = float(v); updated = True
            if updated: 
                save_excel_provinces(SETTINGS['tinh_thanh'])
                msg_update = "✅ Đã cập nhật file Excel!"
            active_tab = 'config'
            
        elif 'btn_delete_province' in request.form and current_role == 'admin':
            t = request.form.get('btn_delete_province')
            if t in SETTINGS['tinh_thanh']:
                del SETTINGS['tinh_thanh'][t]
                save_excel_provinces(SETTINGS['tinh_thanh'])
                msg_update = f"🗑️ Đã xóa {t} khỏi Excel!"
            active_tab = 'config'

        # 7. TÍNH TOÁN & LƯU LỊCH SỬ
        elif 'btn_calc' in request.form:
            try:
                # 1. Lấy dữ liệu từ Form
                ten_kh = request.form.get('ten_khach_hang', 'Khách vãng lai')
                lh, cd = request.form.get('loai_hinh'), request.form.get('che_do_nhap')
                ngu_canh = request.form.get('ngu_canh_chon')
                
                raw_gt = request.form.get('gia_tri_dau_vao')
                gt = float(raw_gt.replace('.', '')) 
                
                hs, tc = float(request.form.get('he_so_nhap') or 0.5), request.form.get('tinh_thanh_chon')
                gn = SETTINGS['tinh_thanh'].get(tc, 4.0)
                gio_nang_da_dung = gn
                
                du_lieu_nhap = {'loai_hinh': lh, 'gia_tri': gt, 'che_do': cd, 'he_so': hs, 'tinh_chon': tc, 'ten_kh': ten_kh}
                
                # 2. Tính toán kết quả
                ket_qua = tinh_toan_kwp(lh, gt, cd, hs, gn, SETTINGS)
                
                # 3. LƯU VÀO EXCEL
                try:
                    thoi_gian = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    map_ten = {
                        'can_ho': 'Hộ Gia Đình',
                        'kinh_doanh': 'Kinh Doanh',
                        'san_xuat': 'Sản Xuất'
                    }
                    ten_co_dau = map_ten.get(lh, lh)
                    kv_mohinh = f"{tc} - {ten_co_dau}"
                    
                    if cd == 'theo_tien': dau_vao_str = f"{raw_gt} VNĐ/Month"
                    else: dau_vao_str = f"{raw_gt} kWh/Month"

                    new_row = {
                        "Tên Khách Hàng": [ten_kh],
                        "Thời Gian": [thoi_gian],
                        "Khu Vực - Mô Hình": [kv_mohinh],
                        "Đầu Vào": [dau_vao_str],
                        "Kết Quả (kWp)": [ket_qua]
                    }
                    df_new = pd.DataFrame(new_row)

                    if os.path.exists(history_path):
                        df_old = pd.read_excel(history_path)
                        df_final = pd.concat([df_old, df_new], ignore_index=True)
                    else: df_final = df_new
                    
                    df_final.to_excel(history_path, index=False)
                    print(f"Đã lưu khách hàng: {ten_kh}")
                    
                except Exception as e_excel:
                    print(f"Lỗi lưu Excel: {e_excel}")

                active_tab = 'calc'
            except Exception as e: 
                print(f"Lỗi tính toán: {e}")
                pass

        # 8. UPLOAD EXCEL
        elif 'btn_upload_excel' in request.form and current_role == 'admin':
            if 'file_excel' not in request.files: msg_update = "❌ Chưa chọn file!"
            else:
                file = request.files['file_excel']
                if file.filename == '': msg_update = "❌ Tên file rỗng!"
                elif file and file.filename.endswith('.xlsx'):
                    try:
                        file.save(excel_path)
                        SETTINGS['tinh_thanh'] = load_excel_provinces()
                        msg_update = "✅ Upload file Excel thành công!"
                    except Exception as e: msg_update = f"❌ Lỗi: {e}"
                else: msg_update = "❌ Chỉ nhận file .xlsx!"
            active_tab = 'config'

    # --- 9. ĐỌC FILE LỊCH SỬ KHÁCH HÀNG ---
    lich_su_data = []
    if os.path.exists(history_path):
        try:
            df_history = pd.read_excel(history_path)
            df_history['id_row'] = df_history.index 
            lich_su_data = df_history.to_dict('records')
            lich_su_data.reverse() 
        except: 
            lich_su_data = []
                
    return render_template('index.html', role=current_role, settings=SETTINGS, users=USERS, ket_qua=ket_qua, du_lieu_nhap=du_lieu_nhap, msg_update=msg_update, active_tab=active_tab, gio_nang_da_dung=gio_nang_da_dung, lich_su=lich_su_data)

# --- ROUTE XÓA DÒNG LỊCH SỬ ---
@app.route('/delete_history', methods=['POST'])
def delete_history():
    if 'user' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403
    
    try:
        row_index = int(request.form.get('row_index'))
        
        if os.path.exists(history_path):
            df = pd.read_excel(history_path)
            if 0 <= row_index < len(df):
                df = df.drop(index=row_index)
                df.to_excel(history_path, index=False)
                
        return redirect(url_for('home', active_tab='history'))
    except Exception as e:
        return f"Lỗi xóa lịch sử: {e}"
        
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18003)