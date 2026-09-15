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

# ================= CẤU HÌNH HỆ THỐNG =================
# BẠN HÃY DÁN LINK GOOGLE SHEETS CỦA BẠN VÀO DẤU NGOẶC KÉP BÊN DƯỚI:
SHEET_URL = "https://drive.google.com/drive/folders/1Qm_aSUDZhuxY_kCot1JhzRCyJsJYLFja"
DRIVE_FOLDER_ID = "kCot1JhzRCyJsJYLFja"

st.set_page_config(page_title="Bách Hóa Sữa Út Huệ", page_icon="🍼", layout="wide")

st.markdown("""
    <style>
    div.stButton > button:first-child { background-color: #0056b3; color: white; font-weight: 600; }
    div.stButton > button:first-child:hover { background-color: #003d82; }
    </style>
""", unsafe_allow_html=True)

DANH_SACH_SAN_PHAM = [
    "Ensure Inmune", "Abbott Grow 110ml", "Pediasure 110ml", 
    "Ensure 800g vani", "Glucerna 220ml (24 chai)", "Glucerna 220ml (30 chai)"
]

# ================= HÀM KẾT NỐI GOOGLE CLOUD =================
@st.cache_resource
def init_google_clients():
    # Lấy chìa khóa JSON từ bảo mật của Streamlit Cloud
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    
    # Quyền truy cập
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    
    # Kết nối Sheets & Drive
    gc = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)
    return gc, drive_service

try:
    gc, drive_service = init_google_clients()
    sheet = gc.open_by_url(SHEET_URL).sheet1
except Exception as e:
    st.error("Chưa cấu hình JSON Keys hoặc Link Google Sheet bị sai.")
    st.stop()

def upload_to_drive(file_buffer, file_name, mime_type):
    media = MediaIoBaseUpload(io.BytesIO(file_buffer), mimetype=mime_type, resumable=True)
    file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    return uploaded_file.get('webViewLink')

# ================= GIAO DIỆN CHÍNH =================
colA, colB = st.columns([1, 8])
with colA: st.markdown("<h1 style='text-align: center; font-size: 50px;'>🍼</h1>", unsafe_allow_html=True)
with colB:
    st.markdown("<h1 style='color: #0056b3;'>Bách Hóa Sữa Út Huệ</h1>", unsafe_allow_html=True)
    st.markdown("**Hệ thống Quản trị Nhập hàng & Lưu trữ Đám mây (Cloud ERP)**")
st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["🛒 Nhập liệu", "📊 Báo cáo", "📈 Phân tích Giá", "🧾 Kho Hóa đơn"])

# --- TAB 1: NHẬP LIỆU ---
with tab1:
    st.subheader("📦 Thêm lô hàng nhập mới")
    col1, col2 = st.columns(2)
    with col1: ngay_nhap = st.date_input("📅 Ngày nhập hàng", datetime.today())
    with col2: hoa_don_files = st.file_uploader("📎 Tải lên ảnh/PDF hóa đơn", accept_multiple_files=True)
    
    if 'input_data' not in st.session_state:
        st.session_state.input_data = pd.DataFrame([{"Tên sản phẩm": DANH_SACH_SAN_PHAM[0], "Số lượng": 1, "Date SP": datetime.today().date(), "Giá nhập": 0}])

    edited_df = st.data_editor(
        st.session_state.input_data,
        column_config={
            "Tên sản phẩm": st.column_config.SelectboxColumn("Tên sản phẩm", options=DANH_SACH_SAN_PHAM, required=True),
            "Số lượng": st.column_config.NumberColumn("Số lượng", min_value=1, step=1, required=True),
            "Date SP": st.column_config.DateColumn("Date SP", format="YYYY/MM/DD", required=True),
            "Giá nhập": st.column_config.NumberColumn("Giá nhập (VNĐ)", min_value=0, step=1000, required=True)
        }, num_rows="dynamic", use_container_width=True, hide_index=True
    )
    
    if st.button("💾 LƯU LÊN ĐÁM MÂY", use_container_width=True):
        with st.spinner("Đang tải dữ liệu lên Google Drive & Sheets... Vui lòng chờ..."):
            # 1. Upload Hóa đơn lên Google Drive
            file_links = []
            if hoa_don_files:
                for file in hoa_don_files:
                    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
                    file_name = f"HD_{timestamp}_{file.name}"
                    link = upload_to_drive(file.getbuffer(), file_name, file.type)
                    file_links.append(link)
            str_links = " | ".join(file_links) if file_links else ""
            
            # 2. Ghi dữ liệu vào Google Sheets
            rows_to_insert = []
            success_count = 0
            for index, row in edited_df.iterrows():
                if pd.notna(row["Tên sản phẩm"]) and row["Số lượng"] > 0:
                    tong_tien = row["Số lượng"] * row["Giá nhập"]
                    # Theo thứ tự cột: Ngày nhập | Tên sản phẩm | Số lượng | Date | Giá nhập | Tổng tiền | Link Hóa đơn
                    rows_to_insert.append([
                        ngay_nhap.strftime("%Y-%m-%d"), 
                        row["Tên sản phẩm"], 
                        row["Số lượng"], 
                        row["Date SP"].strftime("%Y-%m-%d"), 
                        row["Giá nhập"], 
                        tong_tien, 
                        str_links
                    ])
                    success_count += 1
            
            if rows_to_insert:
                sheet.append_rows(rows_to_insert, value_input_option='USER_ENTERED')
                st.success(f"🎉 Đã đẩy thành công {success_count} dòng sản phẩm và hóa đơn lên Cloud!")

# --- CÁC TAB BÁO CÁO (LẤY TỪ GOOGLE SHEETS) ---
# Hàm lấy dữ liệu
def get_data_from_sheets():
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    if not df.empty:
        df['Số lượng'] = pd.to_numeric(df['Số lượng'], errors='coerce').fillna(0)
        df['Giá nhập'] = pd.to_numeric(df['Giá nhập'], errors='coerce').fillna(0)
        df['Tổng tiền'] = pd.to_numeric(df['Tổng tiền'], errors='coerce').fillna(0)
        df['Ngày nhập'] = pd.to_datetime(df['Ngày nhập'], errors='coerce')
    return df

df_db = get_data_from_sheets()

with tab2:
    st.subheader("📊 Dashboard Tổng quan")
    if not df_db.empty:
        col1, col2, col3 = st.columns(3)
        col1.info(f"**📦 Tổng số lô hàng:**\n\n### {len(df_db)}")
        col2.success(f"**🥛 Khối lượng nhập:**\n\n### {df_db['Số lượng'].sum():,.0f} SP")
        col3.warning(f"**💸 Tổng chi phí vốn:**\n\n### {df_db['Tổng tiền'].sum():,.0f} ₫")
        st.dataframe(df_db, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu giao dịch trên Google Sheets.")

with tab3:
    st.subheader("📈 Theo dõi Biến động Giá vốn")
    if not df_db.empty:
        selected_product = st.multiselect("Lọc nhãn hàng", DANH_SACH_SAN_PHAM, default=[DANH_SACH_SAN_PHAM[0]])
        if selected_product:
            mask = df_db['Tên sản phẩm'].isin(selected_product)
            df_filtered = df_db[mask].sort_values(by='Ngày nhập')
            fig = px.line(df_filtered, x='Ngày nhập', y='Giá nhập', color='Tên sản phẩm', markers=True, title="Biểu đồ xu hướng giá nhập")
            st.plotly_chart(fig, use_container_width=True)
            
with tab4:
    st.subheader("🧾 Kho Hóa đơn từ Google Drive")
    st.caption("Nhấp vào link để xem trực tiếp hóa đơn trên Google Drive của bạn.")
    if not df_db.empty and 'Link Hóa đơn' in df_db.columns:
        df_hd = df_db[df_db['Link Hóa đơn'] != ""]
        if not df_hd.empty:
            for index, row in df_hd.iterrows():
                links = row['Link Hóa đơn'].split(" | ")
                ngay = row['Ngày nhập'].strftime("%d/%m/%Y") if pd.notnull(row['Ngày nhập']) else "N/A"
                st.markdown(f"**Hóa đơn ngày: {ngay} (Sản phẩm: {row['Tên sản phẩm']})**")
                for link in links:
                    st.markdown(f"🔗 [Mở xem hóa đơn trên Drive]({link})")
                st.markdown("---")