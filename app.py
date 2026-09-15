import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import json
import io

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ================= 1. CẤU HÌNH HỆ THỐNG =================
st.set_page_config(page_title="Bách Hóa Út Huệ - ERP", page_icon="🍼", layout="wide")

# VUI LÒNG DÁN LINK GOOGLE SHEETS CỦA BẠN VÀO TRONG DẤU NGOẶC KÉP Ở DÒNG DƯỚI ĐÂY:
SHEET_URL = "https://docs.google.com/spreadsheets/d/1US5XRg-SnhQt8dy2CVlBMTifiu0lWjoqYS6Q0_GbbZk/edit?gid=0#gid=0"
DRIVE_FOLDER_ID = "kCot1JhzRCyJsJYLFja"

DANH_SACH_SAN_PHAM = [
    "Ensure Inmune", "Abbott Grow 110ml", "Pediasure 110ml", 
    "Ensure 800g vani", "Glucerna 220ml (24 chai)", "Glucerna 220ml (30 chai)"
]
DANH_SACH_KHO = ["Bách Hóa Út Huệ", "Kho Út Huệ 2"]

st.markdown("""
    <style>
    div.stButton > button:first-child { background-color: #0056b3; color: white; font-weight: 600; border-radius: 8px;}
    div.stButton > button:first-child:hover { background-color: #003d82; }
    .css-1d391kg { background-color: #f8f9fa; } 
    </style>
""", unsafe_allow_html=True)

# ================= 2. KẾT NỐI & DATABASE =================
@st.cache_resource
def init_google_clients():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)
    return gc, drive_service

try:
    gc, drive_service = init_google_clients()
    sh = gc.open_by_url(SHEET_URL)
    sheet_nhaphang = sh.get_worksheet(0) 
    
    try: sheet_nvl = sh.worksheet("ChiPhiNVL")
    except: 
        sheet_nvl = sh.add_worksheet(title="ChiPhiNVL", rows="100", cols="10")
        sheet_nvl.append_row(["Ngày", "Chi tiết", "Số tiền", "Link Hóa đơn"])
        
    try: sheet_tonkho = sh.worksheet("TonKho")
    except:
        sheet_tonkho = sh.add_worksheet(title="TonKho", rows="100", cols="10")
        sheet_tonkho.append_row(["Ngày chốt", "Tên Kho", "Tên sản phẩm", "Số lượng tồn", "Giá nhập", "Tổng giá trị"])
        
    try: sheet_taichinh = sh.worksheet("TaiChinh")
    except:
        sheet_taichinh = sh.add_worksheet(title="TaiChinh", rows="100", cols="10")
        sheet_taichinh.append_row(["Tháng", "Tiền đã rút", "Tiền sàn giữ", "Chi phí khác", "Lợi nhuận cũ"])

except Exception as e:
    st.error(f"Lỗi kết nối: {e}")
    st.stop()

# ĐÃ VÁ LỖI GOOGLE DRIVE CHẶN UPLOAD (resumable=False)
def upload_to_drive(file_buffer, file_name, mime_type):
    media = MediaIoBaseUpload(io.BytesIO(file_buffer), mimetype=mime_type, resumable=False)
    file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    return uploaded_file.get('webViewLink')

def load_df(sheet_obj):
    records = sheet_obj.get_all_records()
    return pd.DataFrame(records)

# ================= 3. SIDEBAR =================
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #0056b3;'>ÚT HUỆ ERP</h2>", unsafe_allow_html=True)
    menu = st.radio("Chọn chức năng:", 
                    ["🛒 Nhập Hàng & Hóa Đơn", 
                     "🛠️ Chi Phí Nguyên Vật Liệu", 
                     "📦 Tồn Kho Thực Tế", 
                     "💰 Tính Lãi / Dòng Tiền", 
                     "📊 Báo Cáo Tổng Hợp"])

# ================= 4. CÁC MÀN HÌNH =================

if menu == "🛒 Nhập Hàng & Hóa Đơn":
    st.header("🛒 Quản lý Nhập Hàng")
    col1, col2 = st.columns(2)
    with col1: ngay_nhap = st.date_input("📅 Ngày nhập hàng", datetime.today())
    with col2: hoa_don_files = st.file_uploader("📎 Tải lên Hóa đơn nhập hàng", accept_multiple_files=True)
    
    # ĐÃ VÁ LỖI KẸT GIAO DIỆN CỘT KHO HÀNG
    if 'input_data' not in st.session_state or "Tên Kho" not in st.session_state.input_data.columns:
        st.session_state.input_data = pd.DataFrame([{"Tên Kho": DANH_SACH_KHO[0], "Tên sản phẩm": DANH_SACH_SAN_PHAM[0], "Số lượng": 1, "Date SP": datetime.today().date(), "Giá nhập": 0}])

    edited_df = st.data_editor(
        st.session_state.input_data,
        column_config={
            "Tên Kho": st.column_config.SelectboxColumn("Tên Kho", options=DANH_SACH_KHO, required=True),
            "Tên sản phẩm": st.column_config.SelectboxColumn("Tên sản phẩm", options=DANH_SACH_SAN_PHAM, required=True),
            "Số lượng": st.column_config.NumberColumn("Số lượng", min_value=1, step=1, required=True),
            "Date SP": st.column_config.DateColumn("Date SP", format="YYYY/MM/DD", required=True),
            "Giá nhập": st.column_config.NumberColumn("Giá nhập (VNĐ)", min_value=0, step=1000, required=True)
        }, num_rows="dynamic", use_container_width=True, hide_index=True
    )
    
    if st.button("💾 LƯU LÔ HÀNG VÀO DATA", use_container_width=True):
        with st.spinner("Đang xử lý hóa đơn và đẩy lên Google..."):
            file_links = []
            if hoa_don_files:
                for f in hoa_don_files:
                    link = upload_to_drive(f.getbuffer(), f"HD_{datetime.now().strftime('%d%m%Y_%H%M%S')}_{f.name}", f.type)
                    file_links.append(link)
            str_links = " | ".join(file_links)
            
            rows_to_insert = []
            for idx, row in edited_df.iterrows():
                if pd.notna(row["Tên sản phẩm"]) and row["Số lượng"] > 0:
                    rows_to_insert.append([
                        ngay_nhap.strftime("%Y-%m-%d"), row["Tên Kho"], row["Tên sản phẩm"], 
                        row["Số lượng"], row["Date SP"].strftime("%Y-%m-%d"), row["Giá nhập"], 
                        row["Số lượng"] * row["Giá nhập"], str_links
                    ])
            if rows_to_insert:
                sheet_nhaphang.append_rows(rows_to_insert, value_input_option='USER_ENTERED')
                st.success(f"🎉 Đã lưu thành công {len(rows_to_insert)} sản phẩm cùng Hóa đơn!")

elif menu == "🛠️ Chi Phí Nguyên Vật Liệu":
    st.header("🛠️ Quản lý Chi Phí Nguyên Vật Liệu")
    with st.form("form_nvl"):
        c1, c2 = st.columns(2)
        with c1:
            ngay_nvl = st.date_input("Ngày chi")
            ten_nvl = st.text_input("Nội dung chi (VD: Băng keo, thùng carton...)")
        with c2:
            tien_nvl = st.number_input("Số tiền chi (VNĐ)", min_value=0, step=10000)
            hd_nvl = st.file_uploader("Tải lên hóa đơn NVL (nếu có)", type=['png', 'jpg', 'jpeg', 'pdf'])
        if st.form_submit_button("💾 LƯU CHI PHÍ NVL", use_container_width=True) and ten_nvl and tien_nvl > 0:
            with st.spinner("Đang lưu..."):
                link_hd_nvl = upload_to_drive(hd_nvl.getbuffer(), f"NVL_{datetime.now().strftime('%d%m%Y')}_{hd_nvl.name}", hd_nvl.type) if hd_nvl else ""
                sheet_nvl.append_row([ngay_nvl.strftime("%Y-%m-%d"), ten_nvl, tien_nvl, link_hd_nvl], value_input_option='USER_ENTERED')
                st.success("✅ Đã lưu chi phí nguyên vật liệu!")
                
    st.divider()
    df_nvl = load_df(sheet_nvl)
    if not df_nvl.empty:
        df_nvl['Số tiền'] = pd.to_numeric(df_nvl['Số tiền'], errors='coerce').fillna(0)
        df_nvl['Ngày'] = pd.to_datetime(df_nvl['Ngày'], errors='coerce')
        df_nvl['Tháng'] = df_nvl['Ngày'].dt.strftime('%m/%Y')
        st.subheader("Bảng Tổng hợp NVL theo Tháng")
        st.dataframe(df_nvl.groupby('Tháng')['Số tiền'].sum().reset_index(), use_container_width=True, hide_index=True)

elif menu == "📦 Tồn Kho Thực Tế":
    st.header("📦 Cập nhật Hàng Tồn Kho Thực Tế")
    ngay_chot = st.date_input("Ngày chốt tồn", datetime.today())
    if 'tonkho_data' not in st.session_state:
        st.session_state.tonkho_data = pd.DataFrame([{"Tên Kho": DANH_SACH_KHO[0], "Tên sản phẩm": DANH_SACH_SAN_PHAM[0], "Số lượng tồn": 0, "Giá nhập": 0}])

    edited_tonkho = st.data_editor(
        st.session_state.tonkho_data,
        column_config={
            "Tên Kho": st.column_config.SelectboxColumn("Tên Kho", options=DANH_SACH_KHO, required=True),
            "Tên sản phẩm": st.column_config.SelectboxColumn("Tên sản phẩm", options=DANH_SACH_SAN_PHAM, required=True),
            "Số lượng tồn": st.column_config.NumberColumn("Số lượng tồn", min_value=0, step=1, required=True),
            "Giá nhập": st.column_config.NumberColumn("Giá nhập vốn", min_value=0, step=1000, required=True)
        }, num_rows="dynamic", use_container_width=True, hide_index=True
    )
    if st.button("💾 CHỐT TỒN KHO", use_container_width=True):
        with st.spinner("Đang chốt kho..."):
            rows_to_insert = []
            tong_von_ton = 0
            for idx, row in edited_tonkho.iterrows():
                if pd.notna(row["Tên sản phẩm"]):
                    gt_ton = row["Số lượng tồn"] * row["Giá nhập"]
                    tong_von_ton += gt_ton
                    rows_to_insert.append([ngay_chot.strftime("%Y-%m-%d"), row["Tên Kho"], row["Tên sản phẩm"], row["Số lượng tồn"], row["Giá nhập"], gt_ton])
            if rows_to_insert:
                sheet_tonkho.append_rows(rows_to_insert, value_input_option='USER_ENTERED')
                st.success(f"✅ Đã chốt tồn! Tổng vốn hàng nằm trong kho: {tong_von_ton:,.0f} VNĐ")

elif menu == "💰 Tính Lãi / Dòng Tiền":
    st.header("💰 Bảng Tính Lãi Thực Tế (P&L)")
    
    st.info("Công thức: (Tiền rút + Sàn giữ) - (Vốn Nhập hàng) - (Chi phí NVL) - (Chi phí khác) + (Giá trị Tồn kho) - (Lời các tháng trước)")
    
    col1, col2 = st.columns(2)
    with col1:
        thang_tinh = st.text_input("Kỳ kế toán (VD: Tháng 9/2026)", value="Tháng 9/2026")
        tien_rut = st.number_input("1. Tổng tiền ĐÃ RÚT từ sàn (Từ lúc bán tới nay)", min_value=0, step=100000)
        tien_giu = st.number_input("2. Số tiền SÀN CÒN GIỮ hiện tại", min_value=0, step=100000)
    with col2:
        chi_phi_khac = st.number_input("3. CÁC CHI PHÍ KHÁC (Marketing, Nhân sự, Phí sàn...)", min_value=0, step=50000)
        loi_nhuan_cu = st.number_input("4. Tổng tiền lời ĐÃ CHỐT của các tháng trước", min_value=0, step=100000)
    
    if st.button("🧮 TÍNH LỢI NHUẬN THỰC TẾ", type="primary", use_container_width=True):
        with st.spinner("Đang tổng hợp số liệu..."):
            df_nhap = load_df(sheet_nhaphang)
            df_nvl = load_df(sheet_nvl)
            df_ton = load_df(sheet_tonkho)
            
            tong_nhap = pd.to_numeric(df_nhap['Tổng tiền'], errors='coerce').sum() if not df_nhap.empty else 0
            tong_nvl = pd.to_numeric(df_nvl['Số tiền'], errors='coerce').sum() if not df_nvl.empty else 0
            
            tong_ton = 0
            if not df_ton.empty:
                df_ton['Ngày chốt'] = pd.to_datetime(df_ton['Ngày chốt'], errors='coerce')
                ngay_chot_cuoi = df_ton['Ngày chốt'].max()
                df_ton_cuoi = df_ton[df_ton['Ngày chốt'] == ngay_chot_cuoi]
                tong_ton = pd.to_numeric(df_ton_cuoi['Tổng giá trị'], errors='coerce').sum()
            
            # Áp dụng công thức
            loi_nhuan_thuc = (tien_rut + tien_giu) - tong_nhap - tong_nvl - chi_phi_khac + tong_ton - loi_nhuan_cu
            tong_chi_phi_all = tong_nhap + tong_nvl + chi_phi_khac
            
            st.divider()
            st.markdown(f"### 🏆 Báo cáo kết quả {thang_tinh}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Doanh thu về (Rút + Giữ)", f"{tien_rut + tien_giu:,.0f} đ")
            c2.metric("Tổng TẤT CẢ Chi phí", f"{tong_chi_phi_all:,.0f} đ", help="Bao gồm: Nhập hàng + NVL + Chi phí khác")
            c3.metric("Giá trị tồn kho hiện tại", f"{tong_ton:,.0f} đ")
            
            if loi_nhuan_thuc > 0:
                st.success(f"## 🚀 LỢI NHUẬN THỰC TẾ: + {loi_nhuan_thuc:,.0f} VNĐ")
            else:
                st.error(f"## 📉 ĐANG ÂM VỐN: {loi_nhuan_thuc:,.0f} VNĐ")
                
            sheet_taichinh.append_row([thang_tinh, tien_rut, tien_giu, chi_phi_khac, loi_nhuan_cu], value_input_option='USER_ENTERED')

elif menu == "📊 Báo Cáo Tổng Hợp":
    st.header("📊 Bảng Điều Khiển Bách Hóa Út Huệ")
    df_db = load_df(sheet_nhaphang)
    if not df_db.empty:
        df_db['Số lượng'] = pd.to_numeric(df_db['Số lượng'], errors='coerce').fillna(0)
        df_db['Tổng tiền'] = pd.to_numeric(df_db['Tổng tiền'], errors='coerce').fillna(0)
        
        st.subheader("1. Cơ cấu Nhập hàng theo Kho")
        tong_kho = df_db.groupby('Tên Kho')['Số lượng'].sum().reset_index()
        st.plotly_chart(px.pie(tong_kho, values='Số lượng', names='Tên Kho', hole=0.4), use_container_width=True)
    else:
        st.info("Chưa có dữ liệu nhập hàng.")
