import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os

# 1. การตั้งค่าหน้าเว็บ
st.set_page_config(layout="wide", page_title="ระบบเปรียบเทียบราคาใบเสนอราคา")

st.title("📊 ระบบสร้างตารางเปรียบเทียบราคาอัตโนมัติ (AI)")
st.markdown("---")
st.markdown("### 💡 วิธีใช้งาน")
st.markdown("1. ใส่ **Gemini API Key** ของคุณ (หากไม่มี สามารถขอฟรีได้ที่ [Google AI Studio](https://aistudio.google.com/))")
st.markdown("2. **อัปโหลดไฟล์ใบเสนอราคา** ของเจ้าต่าง ๆ พร้อมกัน (รองรับทั้งไฟล์ **PDF, JPG, PNG**)")
st.markdown("3. ระบบจะใช้ AI อ่านเอกสาร จับคู่ชื่อสินค้า และสร้างตารางเปรียบเทียบราคาพร้อมไฮไลท์ราคาที่ถูกที่สุดให้ทันที")

# 2. ส่วนรับข้อมูลจากผู้ใช้
st.sidebar.header("🔑 การตั้งค่าระบบ")
api_key = st.sidebar.text_input("ใส่ Google Gemini API Key:", type="password")
st.sidebar.markdown("[👉 คลิกที่นี่เพื่อรับ API Key ฟรี](https://aistudio.google.com/)")

st.markdown("---")
st.subheader("📁 อัปโหลดเอกสารใบเสนอราคา")
uploaded_files = st.file_uploader(
    "เลือกไฟล์ใบเสนอราคา (เลือกพร้อมกันหลายไฟล์ได้)", 
    accept_multiple_files=True, 
    type=['pdf', 'png', 'jpg', 'jpeg']
)

# 3. เริ่มประมวลผลเมื่อกดปุ่ม
if st.button("🚀 เริ่มวิเคราะห์และเปรียบเทียบราคา"):
    if not api_key:
        st.error("❌ กรุณาใส่ Gemini API Key ในแถบด้านซ้ายก่อนเริ่มใช้งาน")
    elif not uploaded_files:
        st.error("❌ กรุณาอัปโหลดไฟล์ใบเสนอราคาอย่างน้อย 1 ไฟล์")
    else:
        try:
            # ตั้งค่าโครงข่าย Gemini API
            genai.configure(api_key=api_key)
            
            # --> ระบบค้นหารุ่น AI ที่พร้อมใช้งานจากบัญชีของคุณอัตโนมัติ (แก้ปัญหา Error 404 100%) <--
            valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            # เลือกรุ่น Flash หรือรุ่นที่ดีที่สุดที่ระบบตรวจพบในบัญชีของคุณ
            selected_model = next((m for m in valid_models if 'flash' in m.lower()), None)
            if not selected_model:
                selected_model = next((m for m in valid_models if 'pro' in m.lower()), valid_models[0])
                
            st.toast(f"🤖 กำลังประมวลผลด้วย AI รุ่น: {selected_model}")
            
            model = genai.GenerativeModel(
                selected_model, 
                generation_config={"response_mime_type": "application/json"}
            )
            
            with st.spinner("⏳ AI กำลังอ่านไฟล์และจัดทำตารางเปรียบเทียบราคา โปรดรอสักครู่... (ใช้เวลาประมาณ 10-30 วินาที)"):
                
                # เตรียมข้อมูลไฟล์ส่งให้ AI
                contents = []
                file_names_clean = []
                
                for file in uploaded_files:
                    bytes_data = file.read()
                    mime_type = file.type
                    contents.append({
                        "mime_type": mime_type,
                        "data": bytes_data
                    })
                    # เก็บชื่อไฟล์แบบตัดนามสกุลออกเพื่อใช้เป็นหัวข้อคอลัมน์
                    clean_name = os.path.splitext(file.name)[0]
                    file_names_clean.append(clean_name)
                
                # สร้างคำสั่ง (Prompt) ควบคุม AI
                file_names_str = ", ".join([f"'{name}'" for name in file_names_clean])
                vendor_keys_json = ", ".join([f'"{name}": ราคาต่อหน่วยของเจ้านี้ (ตัวเลขทศนิยมเท่านั้น ถ้าไม่มีสินค้ารายการนี้ให้ใส่ null)' for name in file_names_clean])
                
                prompt = f"""คุณคือผู้ช่วยฝ่ายจัดซื้อมืออาชีพที่มีความแม่นยำสูงมาก ฉันส่งไฟล์ใบเสนอราคามาให้คุณจำนวน {len(uploaded_files)} ไฟล์ ซึ่งมีชื่อไฟล์ตามลำดับดังนี้: {file_names_str}
                
หน้าที่ของคุณคือ:
1. อ่านข้อมูลรายการสินค้า จำนวน หน่วยนับ และราคาต่อหน่วย (Unit Price) จากทุกไฟล์
2. ทำการจับคู่สินค้าที่มีความหมายหรือเป็นสินค้าชนิดเดียวกัน (แม้ว่าแต่ละเจ้าจะเขียนชื่อไม่เหมือนกัน หรือคนละภาษา) ให้อยู่ในแถว (Row) เดียวกัน
3. ตรวจสอบเรื่องภาษี (VAT): ให้ใช้ราคาต่อหน่วยที่เป็น "ราคาผ่อนผันก่อนรวม VAT" (Before VAT) เสมอ หากเจ้าไหนรวม VAT มาแล้ว ให้คำนวณถอด VAT 7% ออกก่อน เพื่อให้เปรียบเทียบบนฐานเดียวกัน
4. ส่งคืนข้อมูลเป็นรูปแบบ JSON Array ของ Object เท่านั้น ห้ามมีข้อความอื่น โดยใช้โครงสร้างคีย์ดังนี้:
[
  {{
    "Item_Name": "ชื่อสินค้าภาษาไทยที่เข้าใจง่ายและครอบคลุมความหมายของทุกเจ้า",
    "Qty": จำนวนสินค้า (ตัวเลขเท่านั้น),
    "Unit": "หน่วยนับ (เช่น รีม, กล่อง, ตัว, ชิ้น)",
    {vendor_keys_json}
  }}
]

กฎเหล็ก:
- ชื่อคีย์ที่เป็นราคาของแต่ละเจ้า ต้องตรงกับชื่อไฟล์เป๊ะๆ ได้แก่: {file_names_str}
- ห้ามใส่เครื่องหมายคอมม่า (,) ในตัวเลขราคา
- ตรวจสอบตัวเลขให้ถูกต้องแม่นยำ 100% ตามหน้าเอกสาร"""
                
                # ส่งข้อมูลไปประมวลผลที่ Gemini
                response = model.generate_content([prompt] + contents)
                
                # แปลงผลลัพธ์ JSON เป็น DataFrame
                data = json.loads(response.text)
                df = pd.DataFrame(data)
                
                # จัดเรียงลำดับคอลัมน์ให้สวยงาม
                base_cols = ["Item_Name", "Qty", "Unit"]
                vendor_cols = [c for c in df.columns if c not in base_cols]
                df = df[base_cols + vendor_cols]
                
                # เปลี่ยนชื่อหัวคอลัมน์ให้ดูเป็นทางการขึ้น
                display_df = df.rename(columns={
                    "Item_Name": "รายการสินค้า",
                    "Qty": "จำนวน",
                    "Unit": "หน่วยนับ"
                })
                
                # 4. ฟังก์ชันสำหรับไฮไลท์ราคาต่ำสุด (Min) ในแต่ละแถว
                def highlight_min(row):
                    styles = [''] * len(row)
                    row_prices = pd.to_numeric(row[vendor_cols], errors='coerce')
                    
                    if row_prices.notna().any():
                        min_val = row_prices.min()
                        for col_name in vendor_cols:
                            col_idx = row.index.get_loc(col_name)
                            if pd.notna(row[col_name]) and float(row[col_name]) == min_val:
                                styles[col_idx] = 'background-color: #d4edda; color: #155724; font-weight: bold;'
                    return styles

                st.success("✅ วิเคราะห์และเปรียบเทียบราคาสำเร็จ!")
                
                # แสดงตารางเปรียบเทียบราคาต่อหน่วย พร้อมไฮไลท์
                st.subheader("📊 ตารางที่ 1: เปรียบเทียบราคาต่อหน่วย (Before VAT)")
                st.dataframe(display_df.style.apply(highlight_min, axis=1), use_container_width=True)
                
                # 5. สร้างตารางสรุปราคาประหยัดที่สุด (Best Deal)
                st.markdown("---")
                st.subheader("🏆 ตารางที่ 2: สรุปดีลที่ดีที่สุด (Best Deal Summary)")
                
                summary_data = []
                total_saving_budget = 0
                
                for index, row in df.iterrows():
                    row_prices = pd.to_numeric(row[vendor_cols], errors='coerce')
                    if row_prices.notna().any():
                        min_val = row_prices.min()
                        best_vendor = row_prices.idxmin()
                        qty = float(row['Qty']) if pd.notna(row['Qty']) else 1
                        total_item_price = min_val * qty
                        total_saving_budget += total_item_price
                        
                        summary_data.append({
                            "รายการสินค้า": row['Item_Name'],
                            "ราคาต่ำสุดต่อหน่วย": f"{min_val:,.2f} บาท",
                            "ผู้ขายที่ดีที่สุด": best_vendor,
                            "จำนวน": int(qty),
                            "ราคารวมสุทธิ": total_item_price
                        })
                
                summary_df = pd.DataFrame(summary_data)
                
                st.dataframe(
                    summary_df.style.format({"ราคารวมสุทธิ": "{:,.2f} บาท"}), 
                    use_container_width=True
                )
                
                st.info(f"💰 **รวมงบประมาณจัดซื้อที่มีประสิทธิภาพสูงสุด (ราคาถูกที่สุดรวมกัน): {total_saving_budget:,.2f} บาท**")
                
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาดในการประมวลผล: {e}")
            st.info("แนะนำให้ตรวจสอบว่า API Key ถูกต้อง และไฟล์ที่อัปโหลดไม่ชำรุดเสียหายครับ")
