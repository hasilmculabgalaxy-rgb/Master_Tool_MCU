# master_app.py
import streamlit as st
import os
import io
import zipfile
import shutil
import traceback
import tempfile
import time
import base64
import re
from datetime import datetime
import json

import pandas as pd
from PIL import Image, ImageColor, ImageDraw, ImageFont

# PDF libs
PdfReader = PdfWriter = None
try:
    from PyPDF2 import PdfReader, PdfWriter
except Exception:
    pass

pdfplumber = None
try:
    import pdfplumber
except Exception:
    pass

Document = None
try:
    from docx import Document
except Exception:
    pass

# pdf2image
PDF2IMAGE_AVAILABLE = False
convert_from_bytes = convert_from_path = None
try:
    from pdf2image import convert_from_bytes, convert_from_path 
    PDF2IMAGE_AVAILABLE = True
except Exception:
    try:
        from pdf2image import convert_from_path
        PDF2IMAGE_AVAILABLE = True
        convert_from_bytes = None
    except Exception:
        pass

# New imports for translation
Translator = None
try:
    from deep_translator import GoogleTranslator
    Translator = GoogleTranslator
except Exception:
    pass

# QR Code imports
import qrcode

# ----------------- KONFIGURASI DASAR APLIKASI & CSS -----------------
st.set_page_config(
    page_title="Master App – Tools MCU & QR", 
    page_icon="🧰", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* General Styling */
.stApp {
    background-color: #f9fafb;
    font-family: "Inter", sans-serif;
}
.main-header {
    text-align: center;
    padding: 1rem 0;
    color: #1b4f72;
}

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #e5e7eb;
}
.sidebar-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #111827;
    text-align: center;
    margin-bottom: 1rem;
}

/* Card Styling */
.feature-card {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
    margin-bottom: 1rem;
    border: 1px solid #e5e7eb;
    transition: all 0.2s ease-in-out;
}
.feature-card:hover {
    box-shadow: 0 8px 15px rgba(0,0,0,0.12);
    transform: translateY(-2px);
}

/* Button Styling */
div.stButton > button {
    background: linear-gradient(90deg, #5dade2, #3498db);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1rem;
    font-weight: 600;
    transition: 0.2s;
    cursor: pointer;
}
div.stButton > button:hover {
    background: linear-gradient(90deg, #3498db, #2e86c1);
    transform: scale(1.02);
}

/* Footer */
.footer {
    text-align: center;
    color: #9ca3af;
    font-size: 0.9rem;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid #e5e7eb;
}
</style>
""", unsafe_allow_html=True)


# ----------------- FUNGSI BANTU (HELPERS) -----------------
def make_zip_from_map(bytes_map: dict) -> bytes:
    """Membuat file ZIP dari sebuah dictionary {nama_file: data_bytes}."""
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in bytes_map.items():
            z.writestr(name, data)
    b.seek(0)
    return b.getvalue()

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Mengonversi DataFrame ke bytes file Excel."""
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    out.seek(0)
    return out.getvalue()

def show_error_trace(e: Exception):
    """Menampilkan error dan traceback di Streamlit."""
    st.error(f"Terjadi kesalahan: {e}")
    with st.expander("Detail Error (Traceback)"):
        st.code(traceback.format_exc())

def try_encrypt(writer, password: str):
    """Fungsi untuk enkripsi PDF, menampung try/except"""
    try:
        writer.encrypt(password)
    except TypeError:
        try:
            writer.encrypt(user_pwd=password, owner_pwd=None)
        except Exception:
            writer.encrypt(user_pwd=password, owner_pwd=password)

def rotate_page_safe(page, angle):
    """Fungsi untuk rotasi halaman PDF."""
    try:
        page.rotate(angle)
    except Exception:
        try:
            from PyPDF2.generic import NameObject, NumberObject
            page.__setitem__(NameObject("/Rotate"), NumberObject(angle))
        except Exception:
            pass

# ----------------- LOGIKA QR CODE GENERATOR -----------------
def show_qr_generator_page():
    st.header("📱 QR Code Generator Pro")
    st.markdown("Buat QR Code profesional dengan fitur lengkap: logo, warna, batch, dan berbagai tipe QR.")

    if 'qr_history' not in st.session_state:
        st.session_state.qr_history = []

    qr_feature = st.radio("Pilih Fitur:", ["Single QR", "Batch QR", "QR Templates", "Riwayat QR"], horizontal=True)

    if qr_feature == "Single QR":
        _show_single_qr_generator()
    elif qr_feature == "Batch QR":
        _show_batch_qr_generator()
    elif qr_feature == "QR Templates":
        _show_qr_templates()
    elif qr_feature == "Riwayat QR":
        _show_qr_history()

def _show_single_qr_generator():
    st.subheader("Generator QR Code Tunggal")
    qr_type = st.selectbox("Pilih Tipe QR Code:", ["URL/Website", "Teks Biasa", "WiFi", "Email", "SMS", "Telepon", "vCard (Kontak)", "Lokasi Maps", "Event Calendar"])
    
    data = ""
    if qr_type == "URL/Website":
        data = st.text_input("🌐 Masukkan URL:", placeholder="https://example.com")
    elif qr_type == "Teks Biasa":
        data = st.text_area("📝 Masukkan teks:", placeholder="Masukkan teks Anda di sini...")
    elif qr_type == "WiFi":
        col1, col2 = st.columns(2)
        with col1:
            ssid = st.text_input("📶 Nama WiFi (SSID):")
            security = st.selectbox("Keamanan:", ["WPA", "WEP", "nopass"])
        with col2:
            password = st.text_input("🔑 Password:", type="password")
            hidden = st.checkbox("Tersembunyi?")
        if ssid:
            data = f"WIFI:T:{security};S:{ssid};P:{password};H:{'true' if hidden else 'false'};;"
    elif qr_type == "Email":
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("📧 Email:")
            subject = st.text_input("📋 Subjek:")
        with col2:
            body = st.text_area("📝 Isi Email:")
        if email:
            data = f"mailto:{email}?subject={subject}&body={body}"
    elif qr_type == "SMS":
        col1, col2 = st.columns(2)
        with col1:
            phone = st.text_input("📱 Nomor Telepon:")
        with col2:
            message = st.text_area("💬 Pesan:")
        if phone:
            data = f"sms:{phone}?body={message}"
    elif qr_type == "Telepon":
        phone = st.text_input("📱 Nomor Telepon:")
        if phone:
            data = f"tel:{phone}"
    elif qr_type == "vCard (Kontak)":
        with st.expander("📇 Detail Kontak"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("👤 Nama:")
                phone = st.text_input("📱 Telepon:")
                email = st.text_input("📧 Email:")
            with col2:
                company = st.text_input("🏢 Perusahaan:")
                title = st.text_input("💼 Jabatan:")
                website = st.text_input("🌐 Website:")
        if name:
            data = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
TEL:{phone}
EMAIL:{email}
ORG:{company}
TITLE:{title}
URL:{website}
END:VCARD"""
    elif qr_type == "Lokasi Maps":
        col1, col2 = st.columns(2)
        with col1:
            lat = st.text_input("📍 Latitude:")
        with col2:
            lon = st.text_input("📍 Longitude:")
        if lat and lon:
            data = f"geo:{lat},{lon}"
    elif qr_type == "Event Calendar":
        with st.expander("📅 Detail Event"):
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("📋 Judul Event:")
                start = st.text_input("🕐 Mulai (YYYYMMDDTHHMMSS):")
            with col2:
                location = st.text_input("📍 Lokasi:")
                end = st.text_input("🕑 Selesai (YYYYMMDDTHHMMSS):")
        if title and start:
            data = f"""BEGIN:VEVENT
SUMMARY:{title}
DTSTART:{start}
DTEND:{end}
LOCATION:{location}
END:VEVENT"""
    
    st.markdown("### 🎨 Kustomisasi QR Code")
    col1, col2, col3 = st.columns(3)
    with col1:
        uploaded_logo = st.file_uploader("📷 Logo (opsional)", type=["png", "jpg", "jpeg"])
        logo_size = st.slider("Ukuran Logo (%)", 10, 30, 20)
    with col2:
        qr_color = st.color_picker("⚫ Warna QR", "#000000")
        bg_color = st.color_picker("⚪ Warna Background", "#FFFFFF")
    with col3:
        box_size = st.slider("📏 Ukuran Kotak", 5, 20, 10)
        border = st.slider("🔲 Tebal Border", 2, 10, 4)
    
    if st.button("🚀 Buat QR Code", type="primary"):
        if not data:
            st.warning("⚠️ Silakan lengkapi data QR Code terlebih dahulu!")
        else:
            try:
                qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=box_size, border=border)
                qr.add_data(data)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color=qr_color, back_color=bg_color).convert("RGBA")
                
                if uploaded_logo:
                    logo = Image.open(uploaded_logo).convert("RGBA")
                    qr_width, qr_height = qr_img.size
                    logo_size_px = int(qr_width * (logo_size / 100))
                    logo = logo.resize((logo_size_px, logo_size_px), Image.LANCZOS)
                    pos = ((qr_width - logo_size_px) // 2, (qr_height - logo_size_px) // 2)
                    qr_img.paste(logo, pos, logo)

                col1, col2 = st.columns([2, 1])
                with col1:
                    st.image(qr_img, caption="✅ QR Code Hasil", use_container_width=True)
                with col2:
                    st.info("📊 Informasi QR Code")
                    st.json({"Tipe": qr_type, "Ukuran": f"{qr_img.size[0]}x{qr_img.size[1]}px", "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                
                buf = io.BytesIO()
                qr_img.save(buf, format="PNG")
                buf.seek(0)
                
                st.session_state.qr_history.append({'image': buf.getvalue(), 'data': data, 'type': qr_type, 'timestamp': datetime.now()})
                
                st.download_button("📥 Download PNG", data=buf, file_name=f"qrcode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png", mime="image/png")
            except Exception as e:
                st.error(f"Gagal membuat QR Code: {e}")

def _show_batch_qr_generator():
    st.subheader("Generator QR Code Batch")
    uploaded_file = st.file_uploader("📁 Upload CSV/Excel", type=["csv", "xlsx"])
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.dataframe(df.head())
            data_col = st.selectbox("Pilih Kolom Data:", df.columns)
            name_col = st.selectbox("Pilih Kolom Nama (opsional):", [None] + list(df.columns))
            prefix = st.text_input("Prefix Nama File:", value="QR_")
            
            if st.button("🚀 Generate Batch QR Codes"):
                progress = st.progress(0)
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                    for i, row in df.iterrows():
                        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
                        qr.add_data(str(row[data_col]))
                        qr.make(fit=True)
                        qr_img = qr.make_image(fill_color="black", back_color="white")
                        img_buffer = BytesIO()
                        qr_img.save(img_buffer, format="PNG")
                        img_buffer.seek(0)
                        filename = f"{prefix}{row[name_col] if name_col else i+1}.png"
                        zip_file.writestr(filename, img_buffer.getvalue())
                        progress.progress((i + 1) / len(df))
                zip_buffer.seek(0)
                st.download_button("📥 Download All QR Codes (ZIP)", data=zip_buffer.getvalue(), file_name=f"batch_qr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip", mime="application/zip")
                st.success(f"✅ Berhasil generate {len(df)} QR codes!")
        except UnicodeDecodeError:
            st.error("Error: Tidak dapat membaca file. Pastikan file CSV/CSV disimpan dengan encoding UTF-8. Coba buka kembali file di Excel dan simpan sebagai 'CSV UTF-8'.")
        except Exception as e:
            show_error_trace(e)


def _show_qr_templates():
    st.subheader("Template QR Code Siap Pakai")
    templates = {
        "📱 WhatsApp Business": "https://wa.me/628123456789?text=Halo,%20saya%20tertarik%20dengan%20produk%20Anda",
        "📧 Email Signature": "mailto:contact@example.com?subject=Inquiry",
        "📶 WiFi Login": "WIFI:T:WPA;S:MyNetwork;P:MyPassword;H:false;;",
        "📍 Google Maps": "geo:-6.2088,106.8456",
        "📅 Event Registration": "https://eventbrite.com/e/example-event"
    }
    for name, data in templates.items():
        if st.button(f"Gunakan Template: {name}"):
            st.session_state.template_data = data
            st.rerun()
    if 'template_data' in st.session_state:
        st.info(f"Data template '{st.session_state.template_data}' siap digunakan. Pindah ke tab 'Single QR' untuk membuatnya.")

def _show_qr_history():
    st.subheader("📜 Riwayat QR Code")
    if not st.session_state.qr_history:
        st.info("Belum ada riwayat QR Code.")
        return
    for i, item in enumerate(reversed(st.session_state.qr_history)):
        with st.expander(f"📅 {item['timestamp'].strftime('%Y-%m-%d %H:%M')} - {item['type']}"):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(item['image'], width=150)
            with col2:
                st.code(item['data'])
                st.download_button("📥 Download", data=item['image'], file_name=f"qr_history_{i}.png", mime="image/png")


# ----------------- LOGIKA KAY TOOLS (PDF, IMAGE, MCU, FILE) -----------------
def show_kay_tools_page(selected_tool):
    if selected_tool == "📄 PDF Tools":
        _show_pdf_tools_page()
    elif selected_tool == "🖼️ Image Tools":
        _show_image_tools_page()
    elif selected_tool == "📊 MCU Tools":
        _show_mcu_tools_page()
    elif selected_tool == "🗂️ File Tools":
        _show_file_tools_page()
    elif selected_tool == "ℹ️ Tentang Aplikasi":
        _show_about_page()

def _show_pdf_tools_page():
    st.header("📄 PDF Tools")
    pdf_options = ["--- Pilih Tools ---", "Gabung PDF", "Pisah PDF", "Reorder/Hapus Halaman", "Batch Rename PDF (Sequential)", "Batch Rename PDF (Excel)", "Image -> PDF", "PDF -> Image", "Ekstrak Teks/Tabel", "Terjemahan PDF", "Enkripsi PDF"]
    tool_select = st.selectbox("Pilih fitur PDF", pdf_options)

    if tool_select == "Gabung PDF":
        files = st.file_uploader("Upload PDFs (multiple):", type="pdf", accept_multiple_files=True, key="pdf_merge")
        if files and st.button("Gabungkan", key="btn_merge"):
            if PdfWriter is None: st.error("PyPDF2 tidak terinstall."); return
            try:
                writer = PdfWriter()
                for f in files:
                    reader = PdfReader(io.BytesIO(f.read()))
                    for page in reader.pages:
                        writer.add_page(page)
                output = io.BytesIO()
                writer.write(output)
                st.download_button("Unduh Hasil", data=output.getvalue(), file_name="merged.pdf", mime="application/pdf")
                st.success("PDF berhasil digabung.")
            except Exception as e: show_error_trace(e)

    elif tool_select == "Pisah PDF":
        f = st.file_uploader("Upload single PDF:", type="pdf", key="pdf_split")
        if f and st.button("Split to pages (ZIP)"):
            if PdfReader is None: st.error("PyPDF2 tidak terinstall."); return
            try:
                reader = PdfReader(io.BytesIO(f.read()))
                out_map = {}
                for i, page in enumerate(reader.pages):
                    writer = PdfWriter()
                    writer.add_page(page)
                    buf = io.BytesIO()
                    writer.write(buf)
                    out_map[f"page_{i+1}.pdf"] = buf.getvalue()
                zipb = make_zip_from_map(out_map)
                st.download_button("Download pages.zip", zipb, file_name="pages.zip", mime="application/zip")
                st.success("PDF berhasil dipisah.")
            except Exception as e: show_error_trace(e)
    
    elif tool_select == "Reorder/Hapus Halaman":
        st.markdown("#### Reorder atau Hapus Halaman PDF")
        f = st.file_uploader("Unggah 1 file PDF:", type="pdf", key="reorder_pdf_uploader")
        if f:
            try:
                raw = f.read()
                if PdfReader is None: st.error("PyPDF2 tidak terinstall."); st.stop()
                reader = PdfReader(io.BytesIO(raw))
                num_pages = len(reader.pages)
                st.info(f"PDF berhasil dimuat. Jumlah total halaman: **{num_pages}**.")
                default_order = ", ".join(map(str, range(1, num_pages + 1)))
                new_order_str = st.text_input(f"Masukkan urutan halaman baru (1-{num_pages}) dipisahkan koma:", value=default_order)
                if st.button("Proses Reorder/Hapus Halaman", key="process_reorder"):
                    new_order_indices = []
                    try:
                        input_list = [int(x.strip()) for x in new_order_str.split(',') if x.strip().isdigit()]
                        if any(n < 1 or n > num_pages for n in input_list):
                            st.error(f"Nomor halaman harus antara 1 sampai {num_pages}."); st.stop()
                        new_order_indices = [n - 1 for n in input_list]
                        writer = PdfWriter()
                        for index in new_order_indices:
                            writer.add_page(reader.pages[index])
                        pdf_buffer = io.BytesIO()
                        writer.write(pdf_buffer)
                        pdf_buffer.seek(0)
                        st.download_button("Unduh Hasil PDF (Reordered)", data=pdf_buffer, file_name="pdf_reordered.pdf", mime="application/pdf")
                        st.success(f"Pemrosesan selesai. Total halaman baru: {len(new_order_indices)}.")
                    except Exception as e:
                        st.error(f"Format urutan halaman tidak valid atau terjadi kesalahan: {e}")
            except Exception as e:
                st.error(f"Terjadi kesalahan saat memproses PDF: {e}")

    elif tool_select == "Batch Rename PDF (Sequential)":
        st.markdown("#### Ganti Nama File PDF Massal (Sequential)")
        uploaded_files = st.file_uploader("Unggah file PDF (multiple):", type=["pdf"], accept_multiple_files=True, key="batch_rename_pdf_uploader_seq")
        if uploaded_files:
            col1, col2 = st.columns(2)
            new_prefix = col1.text_input("Prefix Nama File Baru:", value="Hasil_PDF", key="prefix_pdf_seq")
            start_num = col2.number_input("Mulai dari Angka:", min_value=1, value=1, step=1, key="start_num_pdf_seq")
            if st.button("Proses Ganti Nama (ZIP)", key="process_batch_rename_pdf_seq"):
                if not new_prefix: st.error("Prefix nama file tidak boleh kosong."); st.stop()
                output_zip = io.BytesIO()
                try:
                    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for i, file in enumerate(uploaded_files, start_num):
                            new_filename = f"{new_prefix}_{i:03d}.pdf"
                            zf.writestr(new_filename, file.read())
                    st.success(f"Berhasil mengganti nama {len(uploaded_files)} file.")
                    st.download_button("Unduh File ZIP Hasil Rename", data=output_zip.getvalue(), file_name="pdf_renamed.zip", mime="application/zip")
                except Exception as e: show_error_trace(e)

    elif tool_select == "Batch Rename PDF (Excel)":
        st.markdown("#### Ganti Nama File PDF Berdasarkan Excel")
        excel_up = st.file_uploader("Unggah Excel/CSV daftar nama:", type=["xlsx", "csv"], key="rename_pdf_excel")
        files = st.file_uploader("Unggah File PDF (multiple):", type=["pdf"], accept_multiple_files=True, key="rename_pdf_files")
        if excel_up and files and st.button("Proses Ganti Nama"):
            try:
                # PERBAIKAN: Menambahkan penanganan error untuk file Excel/CSV
                df = pd.read_csv(io.BytesIO(excel_up.read())) if excel_up.name.lower().endswith(".csv") else pd.read_excel(io.BytesIO(excel_up.read()))
                if not all(col in df.columns for col in ['nama_lama', 'nama_baru']):
                    st.error("Excel/CSV wajib memiliki kolom: 'nama_lama', 'nama_baru'"); return
                file_map = {f.name: f.read() for f in files}
                out_map, not_found = {}, []
                for _, row in df.iterrows():
                    old_name, new_name = str(row['nama_lama']).strip(), str(row['nama_baru']).strip()
                    if old_name in file_map:
                        if not new_name.lower().endswith('.pdf'): new_name += '.pdf'
                        out_map[new_name] = file_map[old_name]
                    else: not_found.append(old_name)
                if out_map:
                    zipb = make_zip_from_map(out_map)
                    st.download_button("Unduh Hasil (ZIP)", zipb, file_name="pdf_renamed.zip", mime="application/zip")
                    st.success(f"{len(out_map)} file berhasil diganti namanya.")
                if not_found: st.warning(f"{len(not_found)} file tidak ditemukan: {not_found[:5]}")
            except UnicodeDecodeError:
                st.error("Error: Tidak dapat membaca file Excel/CSV. Pastikan file disimpan dengan encoding UTF-8. Coba buka kembali file di Excel dan simpan sebagai 'CSV UTF-8' atau 'Workbook'.")
            except Exception as e: show_error_trace(e)
            
    elif tool_select == "Image -> PDF":
        st.markdown("#### Gambar ke PDF")
        imgs = st.file_uploader("Upload images", type=["jpg","png","jpeg"], accept_multiple_files=True)
        if imgs and st.button("Images -> PDF"):
            try:
                with st.spinner("Membuat PDF dari gambar..."):
                    pil = [Image.open(io.BytesIO(i.read())).convert("RGB") for i in imgs]
                    buf = io.BytesIO()
                    if len(pil) == 1:
                        pil[0].save(buf, format="PDF")
                    else:
                        pil[0].save(buf, save_all=True, append_images=pil[1:], format="PDF")
                    buf.seek(0)
                st.download_button("Download images_as_pdf.pdf", buf.getvalue(), file_name="images_as_pdf.pdf", mime="application/pdf")
                st.success("Konversi berhasil.")
            except Exception as e: show_error_trace(e)

    elif tool_select == "PDF -> Image":
        st.markdown("#### PDF ke Gambar (PNG/JPEG)")
        st.info("Memerlukan library `pdf2image` + `poppler` (server).")
        f = st.file_uploader("Upload PDF", type="pdf")
        if f and st.button("Convert to images"):
            try:
                if not PDF2IMAGE_AVAILABLE:
                    st.error("pdf2image not installed or poppler missing."); st.stop()
                with st.spinner("Converting..."):
                    pdf_bytes = f.read()
                    images = convert_from_bytes(pdf_bytes, dpi=150) if convert_from_bytes else convert_from_path(pdf_bytes, dpi=150)
                    out_map = {}
                    for i, img in enumerate(images):
                        b = io.BytesIO(); img.save(b, format="PNG"); out_map[f"page_{i+1}.png"] = b.getvalue()
                    zipb = make_zip_from_map(out_map)
                    st.download_button("Download images.zip", zipb, file_name="pdf_images.zip", mime="application/zip")
                    st.success("Konversi berhasil.")
            except Exception as e: show_error_trace(e)

    elif tool_select == "Ekstrak Teks/Tabel":
        st.markdown("#### Ekstraksi Teks/Tabel dari PDF")
        f = st.file_uploader("Upload PDF", type="pdf")
        if f and st.button("Extract text"):
            try:
                if PdfReader is None and pdfplumber is None: st.error("PyPDF2 atau pdfplumber tidak terinstall."); st.stop()
                with st.spinner("Mengekstrak teks..."):
                    text_blocks = []
                    raw = f.read()
                    if pdfplumber:
                        with pdfplumber.open(io.BytesIO(raw)) as doc:
                            for i, p in enumerate(doc.pages):
                                text_blocks.append(f"--- Page {i+1} ---\n" + (p.extract_text() or ""))
                    else:
                        reader = PdfReader(io.BytesIO(raw))
                        for i, p in enumerate(reader.pages):
                            text_blocks.append(f"--- Page {i+1} ---\n" + (p.extract_text() or ""))
                    full = "\n".join(text_blocks)
                    st.text_area("Extracted text (preview)", full[:10000], height=300)
                    st.download_button("Download .txt", full, file_name="extracted_text.txt", mime="text/plain")
                    st.success("Ekstraksi berhasil.")
            except Exception as e: show_error_trace(e)

    elif tool_select == "Terjemahan PDF":
        st.markdown("#### Terjemahan Teks PDF ke Word")
        st.info("Fitur ini mencoba membuat hasil Word lebih rapi. **Replikasi tata letak kolom/tabel PDF tetap terbatas.**")
        if Translator is None or Document is None:
            if Translator is None: st.error("Library `deep-translator` tidak ditemukan.")
            if Document is None: st.error("Library `python-docx` tidak ditemukan.")
            st.stop()
        f = st.file_uploader("Unggah PDF untuk Diterjemahkan:", type="pdf", key="translate_pdf_uploader")
        col1, col2 = st.columns(2)
        src_lang = col1.text_input("Bahasa Sumber (ISO Code, ex: id)", value="auto")
        target_lang = col2.text_input("Bahasa Tujuan (ISO Code, ex: en, ja, fr)", value="en")
        if f and st.button("Proses Terjemahan dan Buat Word (.docx)", key="translate_pdf_button"):
            try:
                with st.spinner("1. Mengekstrak dan merapikan teks dari PDF..."):
                    raw = f.read()
                    all_text_lines = []
                    if pdfplumber:
                        with pdfplumber.open(io.BytesIO(raw)) as doc:
                            for p in doc.pages:
                                page_text = p.extract_text() or ""
                                all_text_lines.extend(page_text.split('\n'))
                                all_text_lines.append("---HALAMAN BARU---")
                    else:
                        reader = PdfReader(io.BytesIO(raw))
                        for p in reader.pages:
                            page_text = p.extract_text() or ""
                            all_text_lines.extend(page_text.split('\n'))
                            all_text_lines.append("---HALAMAN BARU---")
                    full_text_clean = "\n\n".join(p for p in all_text_lines if p != "---HALAMAN BARU---" and p != "")
                if not full_text_clean.strip():
                    st.warning("Teks kosong atau tidak dapat diekstrak dari PDF."); st.stop()
                with st.spinner(f"2. Menerjemahkan teks ke {target_lang}..."):
                    translator = Translator(source=src_lang, target=target_lang)
                    CHUNK_SIZE = 4500
                    text_chunks_for_translation = []
                    current_chunk = ""
                    for p in all_text_lines:
                        if p == "---HALAMAN BARU---":
                            if current_chunk: text_chunks_for_translation.append(current_chunk)
                            text_chunks_for_translation.append(p)
                            current_chunk = ""
                        elif not p.strip():
                            if current_chunk: text_chunks_for_translation.append(current_chunk)
                            text_chunks_for_translation.append("")
                            current_chunk = ""
                        else:
                            if len(current_chunk) + len(p) + 4 > CHUNK_SIZE:
                                if current_chunk: text_chunks_for_translation.append(current_chunk)
                                current_chunk = p + "\n\n"
                            else:
                                current_chunk += p + "\n\n"
                    if current_chunk: text_chunks_for_translation.append(current_chunk.strip())
                    translated_parts = []
                    prog = st.progress(0)
                    for i, chunk in enumerate(text_chunks_for_translation):
                        if chunk in ("---HALAMAN BARU---", ""):
                            translated_parts.append(chunk)
                        else:
                            if i > 0: time.sleep(0.1)
                            translated = translator.translate(chunk)
                            translated_parts.append(translated.replace(" | ", " | ").strip())
                        prog.progress(int((i + 1) / len(text_chunks_for_translation) * 100))
                    translated_text_combined = "\n\n".join(translated_parts)
                    prog.empty()
                with st.spinner("3. Membuat file Word (.docx) baru..."):
                    doc = Document()
                    for item in translated_text_combined.split('\n\n'):
                        item_stripped = item.strip()
                        if item_stripped == "---HALAMAN BARU---":
                            doc.add_page_break()
                        elif item_stripped:
                            doc.add_paragraph(item_stripped)
                    out = io.BytesIO()
                    doc.save(out)
                    out.seek(0)
                st.success("Terjemahan berhasil! Unduh file Word hasil terjemahan.")
                st.download_button(f"Unduh Hasil Terjemahan ({target_lang}).docx", data=out.getvalue(), file_name=f"translated_to_{target_lang}_rapi.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            except Exception as e:
                st.error(f"Terjadi kesalahan saat terjemahan. Cek kode bahasa dan pastikan teks dapat diekstrak. Error: {e}")
                show_error_trace(e)

    elif tool_select == "Enkripsi PDF":
        st.markdown("#### Kunci (Encrypt) PDF")
        f = st.file_uploader("Upload PDF", type="pdf")
        pw = st.text_input("Password", type="password")
        if f and pw and st.button("Encrypt"):
            try:
                if PdfReader is None: st.error("PyPDF2 tidak terinstall."); st.stop()
                with st.spinner("Mengunci PDF..."):
                    reader = PdfReader(io.BytesIO(f.read()))
                    writer = PdfWriter()
                    for p in reader.pages:
                        writer.add_page(p)
                    try_encrypt(writer, pw)
                    buf = io.BytesIO(); writer.write(buf); buf.seek(0)
                st.download_button("Download encrypted.pdf", buf.getvalue(), file_name="encrypted.pdf", mime="application/pdf")
                st.success("PDF berhasil dienkripsi.")
            except Exception as e: show_error_trace(e)


def _show_image_tools_page():
    st.header("🖼️ Image Tools")
    img_tool = st.selectbox("Pilih Fitur Gambar", ["Kompres Foto (Batch)", "Batch Rename Gambar (Sequential)", "Batch Rename Gambar (Excel)"])
    
    if img_tool == "Kompres Foto (Batch)":
        uploaded = st.file_uploader("Unggah gambar (jpg/png) — bisa banyak", type=["jpg","jpeg","png"], accept_multiple_files=True)
        quality = st.slider("Kualitas JPEG", 10, 95, 75)
        max_side = st.number_input("Max side (px)", 100, 4000, 1200)
        if uploaded and st.button("Kompres Semua"):
            out_map = {}
            for i, f in enumerate(uploaded):
                try:
                    im = Image.open(io.BytesIO(f.read()))
                    im.thumbnail((max_side, max_side))
                    buf = io.BytesIO()
                    im.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
                    out_map[f"compressed_{f.name}"] = buf.getvalue()
                except Exception as e: st.warning(f"Gagal: {f.name} — {e}")
            if out_map:
                zipb = make_zip_from_map(out_map)
                st.download_button("Unduh Hasil (ZIP)", zipb, file_name="foto_kompres.zip", mime="application/zip")
                st.success("Kompresi selesai.")

    elif img_tool == "Batch Rename Gambar (Sequential)":
        uploaded_files = st.file_uploader("Unggah file Gambar (JPG, PNG, dll.):", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key="batch_rename_uploader")
        if uploaded_files:
            col1, col2 = st.columns(2)
            new_prefix = col1.text_input("Prefix Nama File Baru:", value="KAY_File", key="prefix_img_seq")
            new_format = col2.selectbox("Format Output Baru:", ["Sama seperti Asli", "JPG", "PNG", "WEBP"], index=0, key="format_img_seq")
            if st.button("Proses Batch File", key="process_batch_rename_seq"):
                if not new_prefix: st.error("Prefix nama file tidak boleh kosong."); st.stop()
                output_zip = io.BytesIO()
                try:
                    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for i, file in enumerate(uploaded_files, 1):
                            _, original_ext = os.path.splitext(file.name)
                            img = Image.open(file)
                            img_io = io.BytesIO()
                            if new_format == "Sama seperti Asli":
                                output_format_pil = img.format if img.format else 'JPEG'
                                output_ext = original_ext
                            else:
                                output_ext = "." + new_format.lower()
                                output_format_pil = new_format.upper()
                            new_filename = f"{new_prefix}_{i:03d}{output_ext}"
                            if output_format_pil in ('JPEG', 'JPG'):
                                img.convert("RGB").save(img_io, format='JPEG', quality=95)
                            elif output_format_pil == 'PNG':
                                img.save(img_io, format='PNG')
                            elif output_format_pil == 'WEBP':
                                img.save(img_io, format='WEBP')
                            else:
                                img.save(img_io, format=output_format_pil)
                            img_io.seek(0)
                            zf.writestr(new_filename, img_io.read())
                    st.success(f"Berhasil memproses {len(uploaded_files)} file.")
                    st.download_button("Unduh File ZIP Hasil Batch", data=output_zip.getvalue(), file_name="hasil_batch_gambar.zip", mime="application/zip")
                except Exception as e: show_error_trace(e)

    elif img_tool == "Batch Rename Gambar (Excel)":
        st.markdown("#### Ganti Nama Gambar (PNG/JPEG) Berdasarkan Excel")
        st.info("Template Excel/CSV wajib memiliki kolom **`nama_lama`** dan **`nama_baru`**.")
        excel_up = st.file_uploader("Unggah Excel/CSV untuk daftar nama:", type=["xlsx", "csv"], key="rename_img_excel_up")
        files = st.file_uploader("Unggah Gambar (JPG/PNG/JPEG, multiple):", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="rename_img_files_up")
        if excel_up and files and st.button("Proses Ganti Nama Gambar (ZIP)", key="process_img_rename_excel"):
            try:
                # PERBAIKAN: Menambahkan penanganan error untuk file Excel/CSV
                df = pd.read_csv(io.BytesIO(excel_up.read())) if excel_up.name.lower().endswith(".csv") else pd.read_excel(io.BytesIO(excel_up.read()))
                required_cols = ['nama_lama', 'nama_baru']
                if not all(col in df.columns for col in required_cols):
                    st.error(f"Excel/CSV wajib memiliki kolom: {', '.join(required_cols)}"); st.stop()
                file_map = {f.name: f.read() for f in files}
                out_map, not_found = {}, []
                df['nama_lama_str'] = df['nama_lama'].astype(str).str.strip()
                for _, row in df.iterrows():
                    old_name = str(row['nama_lama']).strip()
                    new_name = str(row['nama_baru']).strip()
                    if old_name in file_map:
                        if not os.path.splitext(new_name)[1]:
                            _, old_ext = os.path.splitext(old_name)
                            new_name = new_name + old_ext
                        out_map[new_name] = file_map[old_name]
                    else:
                        not_found.append(old_name)
                if out_map:
                    zipb = make_zip_from_map(out_map)
                    st.download_button("Unduh Hasil (ZIP)", zipb, file_name="gambar_renamed_by_excel.zip", mime="application/zip")
                    st.success(f"{len(out_map)} file berhasil diganti namanya.")
                if not_found:
                    st.info(f"{len(not_found)} file 'nama_lama' di Excel tidak ditemukan. Contoh: {not_found[:5]}")
            except UnicodeDecodeError:
                st.error("Error: Tidak dapat membaca file Excel/CSV. Pastikan file disimpan dengan encoding UTF-8. Coba buka kembali file di Excel dan simpan sebagai 'CSV UTF-8' atau 'Workbook'.")
            except Exception as e: show_error_trace(e)


def _show_mcu_tools_page():
    st.header("📊 MCU Tools")
    st.warning("Fitur ini membutuhkan template Excel/PDF khusus untuk analisis. Pastikan format input data Anda sesuai.")
    mcu_tool = st.selectbox("Pilih Fitur MCU", ["Dashboard Analisis Data MCU", "Organise by Excel"], index=0)
    
    if mcu_tool == "Dashboard Analisis Data MCU":
        st.subheader("Dashboard Analisis Hasil MCU Massal")
        uploaded_file = st.file_uploader("Unggah file Data MCU (Excel/CSV):", type=["xlsx", "csv"], key="mcu_data_uploader_new")
        if uploaded_file:
            try:
                # PERBAIKAN: Menambahkan penanganan error untuk file Excel/CSV
                with st.spinner("Membaca data dan normalisasi kolom..."):
                    df = pd.read_csv(io.BytesIO(uploaded_file.read())) if uploaded_file.name.lower().endswith('.csv') else pd.read_excel(io.BytesIO(uploaded_file.read()))
                    st.success(f"Data berhasil dimuat. Total Baris: {len(df)}")
                    df.columns = df.columns.str.replace('[^A-Za-z0-9_]+', '', regex=True).str.lower()
                st.markdown("#### Preview Data (5 Baris Teratas)")
                st.dataframe(df.head(), use_container_width=True)
                st.markdown("---")
                st.markdown("### Visualisasi & Analisis Cepat Status")
                status_cols = [col for col in df.columns if 'status' in col or 'fit' in col or 'hasil' in col]
                if status_cols:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        status_col = st.selectbox("Pilih Kolom Utama Status/Hasil:", status_cols, index=0, key="select_status_col")
                    st.markdown(f"##### 1. Distribusi Status Kesehatan (`{status_col}`)")
                    df[status_col] = df[status_col].astype(str).str.strip().str.upper().fillna("TIDAK DIKETAHUI")
                    status_counts = df[status_col].value_counts().reset_index()
                    status_counts.columns = [status_col, 'Jumlah']
                    status_counts = status_counts.sort_values(by='Jumlah', ascending=False)
                    if len(status_counts) > 0:
                        st.dataframe(status_counts, use_container_width=True)
                        st.bar_chart(status_counts.set_index(status_col))
                        excel_bytes = df_to_excel_bytes(status_counts)
                        st.download_button("Unduh Data Agregasi Status (Excel)", data=excel_bytes, file_name="status_agregat.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    else:
                        st.info("Kolom status/hasil tidak memiliki data unik yang valid.")
                else:
                    st.warning("Kolom yang mengandung kata 'status', 'fit', atau 'hasil' tidak ditemukan.")
            except UnicodeDecodeError:
                st.error("Error: Tidak dapat membaca file Excel/CSV. Pastikan file disimpan dengan encoding UTF-8. Coba buka kembali file di Excel dan simpan sebagai 'CSV UTF-8' atau 'Workbook'.")
            except Exception as e: show_error_trace(e)

    elif mcu_tool == "Organise by Excel":
        st.subheader("Organise by Excel (Original Logic)")
        st.info("Fitur ini akan membuat struktur folder di dalam file ZIP berdasarkan data Excel dan nama file PDF yang diunggah.")
        excel_up = st.file_uploader("Upload Excel (No_MCU, Nama, Departemen, JABATAN) or (filename,target_folder)", type=["xlsx","csv"], key="mcu_organize_excel")
        pdfs = st.file_uploader("Upload PDF files (multiple)", type="pdf", accept_multiple_files=True, key="mcu_organize_pdf")
        if excel_up and pdfs and st.button("Process MCU"):
            try:
                # PERBAIKAN: Menambahkan penanganan error untuk file Excel/CSV
                with st.spinner("Memproses MCU..."):
                    df = pd.read_csv(io.BytesIO(excel_up.read())) if excel_up.name.lower().endswith(".csv") else pd.read_excel(io.BytesIO(excel_up.read()))
                    pdf_map = {p.name: p.read() for p in pdfs}
                    out_map, not_found = {}, []
                    if all(c in df.columns for c in ["No_MCU","Nama","Departemen","JABATAN"]):
                        st.info("Mode: Organisasi berdasarkan kolom **No_MCU, Departemen, JABATAN**.")
                        for _, r in df.iterrows():
                            no = str(r["No_MCU"]).strip()
                            dept = str(r["Departemen"]).strip().replace('/', '_').replace('\\', '_') if not pd.isna(r["Departemen"]) else "Unknown_Dept"
                            jab = str(r["JABATAN"]).strip().replace('/', '_').replace('\\', '_') if not pd.isna(r["JABATAN"]) else "Unknown_JABATAN"
                            matches = [k for k in pdf_map.keys() if k.startswith(no)]
                            if matches:
                                out_map[f"{dept}/{jab}/{matches[0]}"] = pdf_map[matches[0]]
                            else:
                                not_found.append(no)
                    elif "filename" in df.columns and "target_folder" in df.columns:
                        st.info("Mode: Organisasi berdasarkan kolom **filename** dan **target_folder**.")
                        for _, r in df.iterrows():
                            fn = str(r["filename"]).strip()
                            tgt = str(r["target_folder"]).strip().replace('/', '_').replace('\\', '_')
                            if fn in pdf_map:
                                out_map[f"{tgt}/{fn}"] = pdf_map[fn]
                            else:
                                not_found.append(fn)
                    else:
                        st.error("Format Excel/CSV tidak valid.")
                if out_map:
                    zipb = make_zip_from_map(out_map)
                    st.download_button("Download MCU zip", zipb, file_name="mcu_structured.zip", mime="application/zip")
                    st.success(f"{len(out_map)} file berhasil diproses.")
                if not_found:
                    st.warning(f"{len(not_found)} ID/File tidak ditemukan. Contoh: {not_found[:10]}")
            except UnicodeDecodeError:
                st.error("Error: Tidak dapat membaca file Excel/CSV. Pastikan file disimpan dengan encoding UTF-8. Coba buka kembali file di Excel dan simpan sebagai 'CSV UTF-8' atau 'Workbook'.")
            except Exception as e: show_error_trace(e)


def _show_file_tools_page():
    st.header("🗂️ File Tools")
    file_tool = st.selectbox("Pilih Fitur File", ["Zip / Unzip File", "Konversi Dasar ke Excel"])
    if file_tool == "Zip / Unzip File":
        mode = st.radio("Pilih Mode", ["Compress to ZIP", "Extract from ZIP"])
        if mode == "Compress to ZIP":
            files = st.file_uploader("Unggah File (Multiple)", accept_multiple_files=True)
            if files and st.button("Buat ZIP"):
                try:
                    out_map = {f.name: f.read() for f in files}
                    zipb = make_zip_from_map(out_map)
                    st.download_button("Unduh ZIP", zipb, file_name="compressed_files.zip", mime="application/zip")
                    st.success("Kompresi selesai.")
                except Exception as e: show_error_trace(e)
        elif mode == "Extract from ZIP":
            f = st.file_uploader("Unggah File ZIP", type=["zip"])
            if f and st.button("Ekstrak ke Folder/ZIP"):
                try:
                    z = zipfile.ZipFile(io.BytesIO(f.read()))
                    extracted_files = {}
                    for name in z.namelist():
                        if not name.endswith('/'):
                            extracted_files[name] = z.read(name)
                    if extracted_files:
                        st.download_button("Unduh Hasil Ekstraksi (ZIP)", make_zip_from_map(extracted_files), file_name="extracted_content.zip", mime="application/zip")
                        st.info(f"{len(extracted_files)} file berhasil diekstrak.")
                    else:
                        st.warning("File ZIP kosong.")
                except Exception as e: show_error_trace(e)
    elif file_tool == "Konversi Dasar ke Excel":
        st.subheader("Konversi Data ke Excel")
        f = st.file_uploader("Unggah file (TXT, CSV, JSON)", type=["txt", "csv", "json"])
        if f:
            df = None
            try:
                # PERBAIKAN: Menambahkan penanganan error untuk file Excel/CSV
                if f.name.lower().endswith(".csv"):
                    df = pd.read_csv(io.BytesIO(f.read()))
                elif f.name.lower().endswith(".json"):
                    df = pd.read_json(io.BytesIO(f.read()))
                elif f.name.lower().endswith(".txt"):
                    df = pd.read_csv(io.BytesIO(f.read()))
                if df is not None:
                    st.dataframe(df.head())
                    if st.button("Konversi ke Excel"):
                        excel_bytes = df_to_excel_bytes(df)
                        st.download_button("Unduh Excel", excel_bytes, file_name="converted_file.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        st.success("Konversi berhasil.")
            except UnicodeDecodeError:
                st.error("Error: Tidak dapat membaca file. Pastikan file (khususnya CSV/TXT) disimpan dengan encoding UTF-8. Coba buka kembali file di editor teks dan simpan dengan encoding UTF-8.")
            except Exception as e: show_error_trace(e)

def _show_about_page():
    st.header("ℹ️ Tentang Aplikasi")
    st.markdown("""
    **Master App – Tools** adalah aplikasi serbaguna berbasis Streamlit untuk membantu:
    -  **QR Code Generator Pro**: Membuat berbagai jenis QR.
    -  **Pengolahan Dokumen PDF** (gabung, pisah, proteksi, ekstraksi, Reorder/Hapus Halaman, Batch Rename, Terjemahan)
    -  **Analisis & Pengolahan Hasil MCU** (Dashboard Analisis Data, Organise by Excel)
    -  **Manajemen File & Konversi Dasar** (Batch Rename/Format Gambar, Batch Rename PDF)
    
    ### Kebutuhan Library Tambahan
    Beberapa fitur memerlukan library tambahan (instal di environment Anda):
    - `PyPDF2` (Dasar PDF): `pip install PyPDF2`
    - `pdfplumber` untuk ekstraksi tabel teks: `pip install pdfplumber`
    - `python-docx` untuk menghasilkan .docx: `pip install python-docx`
    - `deep-translator` untuk fitur terjemahan PDF: `pip install deep-translator`
    - `pdf2image` + poppler untuk konversi PDF->Gambar: `pip install pdf2image`
    - `pandas` & `openpyxl` untuk Analisis MCU dan Batch Rename: `pip install pandas openpyxl`
    - `qrcode[pil]` untuk generator QR: `pip install qrcode[pil]`
    """)
    st.info("Data diproses di server tempat Streamlit dijalankan. Untuk mengaktifkan semua fitur, pasang dependensi yang diperlukan.")


# ----------------- NAVIGASI UTAMA -----------------
with st.sidebar:
    st.markdown('<div class="sidebar-title">🧰 Master App</div>', unsafe_allow_html=True)
    page = st.selectbox(
        "Pilih Kategori Tools:",
        [
            "🏠 Dashboard",
            "---",
            "📱 QR Code Generator Pro",
            "---",
            "📄 PDF Tools",
            "🖼️ Image Tools",
            "📊 MCU Tools",
            "🗂️ File Tools",
            "---",
            "ℹ️ Tentang Aplikasi"
        ]
    )

# ----------------- KONTEN UTAMA -----------------
st.markdown('<div class="main-header"><h1>Selamat Datang di Master App</h1></div>', unsafe_allow_html=True)
st.markdown("---")

if page == "🏠 Dashboard":
    st.header("🏠 Dashboard")
    st.markdown("Pilih fitur yang ingin Anda gunakan dari menu di sidebar.")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="feature-card">
            <h3>📱 QR Code Generator Pro</h3>
            <p>Buat QR Code profesional dengan logo, warna, dan berbagai tipe data. Mendukung pembuatan batch dari CSV/Excel.</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="feature-card">
            <h3>📄 KAY App - Document Tools</h3>
            <p>Alat lengkap untuk pengolahan dokumen, PDF, gambar, dan analisis data MCU.</p>
        </div>
        """, unsafe_allow_html=True)

elif page == "📱 QR Code Generator Pro":
    show_qr_generator_page()

elif page in ["📄 PDF Tools", "🖼️ Image Tools", "📊 MCU Tools", "🗂️ File Tools", "ℹ️ Tentang Aplikasi"]:
    show_kay_tools_page(page)

# ----------------- FOOTER -----------------
st.markdown("---")
st.markdown('<div class="footer">Developed by AR - 2025</div>', unsafe_allow_html=True)
