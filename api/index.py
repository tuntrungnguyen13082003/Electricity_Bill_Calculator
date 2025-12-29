import os
from flask import Flask, render_template, request

# --- CẤU HÌNH ĐƯỜNG DẪN CHUẨN ---
base_dir = os.path.abspath(os.path.dirname(__file__))
template_path = os.path.join(base_dir, 'templates')
app = Flask(__name__, template_folder=template_path)

# --- HÀM TÍNH NGƯỢC TIỀN ĐIỆN THEO BẬC THANG EVN ---
def tinh_nguoc_kwh_evn(tong_tien):
    # Giá bán lẻ điện sinh hoạt (Chưa VAT) - Cập nhật mới nhất
    # Bậc 1: 0-50 kWh: 1806 đ
    # Bậc 2: 51-100 kWh: 1866 đ
    # Bậc 3: 101-200 kWh: 2167 đ
    # Bậc 4: 201-300 kWh: 2729 đ
    # Bậc 5: 301-400 kWh: 3050 đ
    # Bậc 6: 401 trở lên: 3151 đ
    
    VAT = 1.08 # Thuế GTGT 8% (Bạn có thể sửa thành 1.1 nếu thuế 10%)
    
    # Cấu trúc: (Số kWh của bậc, Giá đã có thuế)
    bac_thang = [
        (50, 1984 * VAT),
        (50, 2050 * VAT), # 50 số tiếp theo
        (100, 2380 * VAT), # 100 số tiếp theo
        (100, 2998 * VAT),
        (100, 3350 * VAT),
        (float('inf'), 3460 * VAT) # Bậc cuối cùng vô tận
    ]

    kwh_tich_luy = 0
    tien_con_lai = tong_tien

    for so_kwh_cua_bac, gia_bac in bac_thang:
        tien_max_cua_bac = so_kwh_cua_bac * gia_bac
        
        if tien_con_lai > tien_max_cua_bac:
            # Nếu tiền còn lại nhiều hơn tiền max của bậc này -> Cộng full bậc
            kwh_tich_luy += so_kwh_cua_bac
            tien_con_lai -= tien_max_cua_bac
        else:
            # Nếu tiền còn lại ít hơn -> Chia ra số kWh lẻ rồi dừng
            kwh_tich_luy += tien_con_lai / gia_bac
            tien_con_lai = 0
            break
            
    return kwh_tich_luy

# --- HÀM TÍNH TOÁN CHÍNH ---
def tinh_toan_kwp(loai_hinh, tien_dien, gia_dien_nhap_tay=0):
    kWh = 0
    
    if loai_hinh == 'can_ho':
        # Tính theo bậc thang EVN
        kWh = tinh_nguoc_kwh_evn(tien_dien)
    else:
        # Kinh doanh hoặc Sản xuất -> Dùng giá nhập tay
        # Tránh chia cho 0
        if gia_dien_nhap_tay > 0:
            kWh = tien_dien / gia_dien_nhap_tay
        else:
            return 0

    # Công thức tính kWp của bạn
    kwp = ((kWh * 0.5) / 30) / 24
    
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
            
            # Lấy giá điện nhập tay (nếu có), mặc định là 0
            gia_dien_input = request.form.get('gia_dien_khac')
            gia_dien_khac = float(gia_dien_input) if gia_dien_input else 0

            du_lieu_nhap = {
                'loai_hinh': loai_hinh, 
                'tien_dien': tien_dien,
                'gia_dien_khac': gia_dien_khac
            }
            
            ket_qua = tinh_toan_kwp(loai_hinh, tien_dien, gia_dien_khac)
        except ValueError:
            pass 

    return render_template('index.html', ket_qua=ket_qua, du_lieu_nhap=du_lieu_nhap)

if __name__ == '__main__':
    app.run(debug=True)