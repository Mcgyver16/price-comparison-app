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
st.markdown("1. ใส่ **Gemini API Key** ของคุณ")
st.markdown("2. **อัปโหลดไฟล์ใบเสนอราคา** ของเจ้าต่าง ๆ พร้อมกัน (รองรับทั้งไฟล์ **PDF, JPG, PNG**)")
st.markdown("3. ระบบจะใช้ AI อ่านเอกสาร จับคู่ชื่อสินค้า และสร้างตารางเปรียบเทียบราคาแบบละเอียดให้ทันที")

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
            genai.configure(api_key=api_key)
            
            valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            selected_model = next((m for m in valid_models if 'flash' in m.lower()), None)
            if not selected_model:
                selected_model = next((m for m in valid_models if 'pro' in m.lower()), valid_models[0])
                
            st.toast(f"🤖 กำลังประมวลผลด้วย AI รุ่น: {selected_model}")
            
            model = genai.GenerativeModel(
                selected_model, 
                generation_config={"response_mime_type": "application/json"}
            )
            
            with st.spinner("⏳ AI กำลังอ่านไฟล์และจัดทำตารางเปรียบเทียบราคาแบบละเอียด โปรดรอสักครู่..."):
                
                contents = []
                file_names_clean = []
                
                for file in uploaded_files:
                    bytes_data = file.read()
                    mime_type = file.type
                    contents.append({
                        "mime_type": mime_type,
                        "data": bytes_data
                    })
                    clean_name = os.path.splitext(file.name)[0]
                    file_names_clean.append(clean_name)
                
                file_names_str = ", ".join([f"'{name}'" for name in file_names_clean])
                
                # โครงสร้าง JSON ที่ต้องการให้ AI ดึงมา (เพิ่ม Discount, VAT)
                vendor_structure = ", ".join([
                    f'"{name}_UnitPrice": "ราคาต่อหน่วยของเจ้านี้ (ก่อน VAT ตัวเลขทศนิยม ถ้าไม่มีใส่ null)", '
                    f'"{name}_Discount": "ส่วนลดต่อหน่วยหรือส่วนลดเฉลี่ยต่อหน่วยของสินค้านี้จากเจ้านี้ (ถ้าไม่มีส่วนลดให้ใส่ 0)", '
                    f'"{name}_VAT_Rate": "อัตรา VAT เช่น 7 หรือ 0 (ถ้ามี VAT 7% ให้ใส่ 7, ถ้าไม่มีหรือไม่คิดให้ใส่ 0)"' 
                    for name in file_names_clean
                ])
                
                prompt = f"""คุณคือผู้ช่วยฝ่ายจัดซื้อมืออาชีพที่มีความแม่นยำสูงมาก ฉันส่งไฟล์ใบเสนอราคามาให้คุณจำนวน {len(uploaded_files)} ไฟล์ ซึ่งมีชื่อไฟล์ตามลำดับดังนี้: {file_names_str}
                
หน้าที่ของคุณคือ:
1. อ่านข้อมูลรายการสินค้า จำนวน หน่วยนับ และราคาต่อหน่วย (Unit Price) จากทุกไฟล์
2. ทำการจับคู่สินค้าที่มีความหมายหรือเป็นสินค้าชนิดเดียวกัน (แม้ว่าแต่ละเจ้าจะเขียนชื่อไม่เหมือนกัน หรือคนละภาษา) ให้อยู่ในแถว (Row) เดียวกัน
3. ตรวจสอบรายละเอียดเรื่องราคาและภาษี:
   - ดึง "ราคาต่อหน่วยก่อน VAT" (Before VAT)
   - ดึง "ส่วนลดของรายการสินค้านั้น" (หากเป็นส่วนลดท้ายบิล ให้เฉลี่ยหรือถ้าไม่มีส่วนลดรายชิ้นให้ใส่ 0)
   - ตรวจสอบว่าใบเสนอราคานั้นคิด VAT 7% หรือ 0% (ไม่คิด VAT)
4. ส่งคืนข้อมูลเป็นรูปแบบ JSON Array ของ Object เท่านั้น ห้ามมีข้อความอื่น โดยใช้โครงสร้างคีย์ดังนี้:
[
  {{
    "Item_Name": "ชื่อสินค้าภาษาไทยหรืออังกฤษที่เข้าใจง่ายครอบคลุมความหมายของทุกเจ้า",
    "Qty": จำนวนสินค้า (ตัวเลขเท่านั้น),
    "Unit": "หน่วยนับ (เช่น รีม, กล่อง, ตัว, ชิ้น, ม.),",
    {vendor_structure}
  }}
]

กฎเหล็ก:
- ชื่อคีย์ต้องตรงตามโครงสร้างเป๊ะๆ 
- ห้ามใส่เครื่องหมายคอมม่า (,) ในตัวเลขราคา
- ตรวจสอบตัวเลขให้ถูกต้องแม่นยำ 100% ตามหน้าเอกสาร"""
                
                response = model.generate_content([prompt] + contents)
                
                data = json.loads(response.text)
                df = pd.DataFrame(data)
                
                # ฟังก์ชันคำนวณราคาคอลัมน์ต่างๆ ให้ครบถ้วนใน Pandas
                qty_col = pd.to_numeric(df['Qty'], errors='coerce').fillna(1)
                
                for name in file_names_clean:
                    up_col = f"{name}_UnitPrice"
                    disc_col = f"{name}_Discount"
                    vat_col = f"{name}_VAT_Rate"
                    
                    df[up_col] = pd.to_numeric(df.get(up_col, 0), errors='coerce').fillna(0)
                    df[disc_col] = pd.to_numeric(df.get(disc_col, 0), errors='coerce').fillna(0)
                    df[vat_col] = pd.to_numeric(df.get(vat_col, 0), errors='coerce').fillna(0)
                    
                    # คำนวณยอดต่างๆ
                    total_before_disc = qty_col * df[up_col]
                    total_disc = qty_col * df[disc_col]
                    after_disc = total_before_disc - total_disc
                    vat_val = after_disc * (df[vat_col] / 100.0)
                    net_total = after_disc + vat_val
                    
                    # เซฟกลับเข้า DataFrame
                    df[f"{name}_Total"] = total_before_disc
                    df[f"{name}_TotalDiscount"] = total_disc
                    df[f"{name}_AfterDisc"] = after_disc
                    df[f"{name}_VAT_Val"] = vat_val
                    df[f"{name}_NetTotal"] = net_total
                
                st.success("✅ วิเคราะห์และเปรียบเทียบราคาแบบละเอียดสำเร็จ!")
                
                # ---------------------------------------------------------
                # ส่วนแสดงผลตารางที่ 1: ตารางเปรียบเทียบราคาต่อหน่วย (Min Unit Price)
                # ---------------------------------------------------------
                st.subheader("📊 ตารางที่ 1: เปรียบเทียบราคาต่อหน่วย (Unit Price - ก่อน VAT)")
                
                unit_cols = [f"{name}_UnitPrice" for name in file_names_clean]
                display_unit_df = df[["Item_Name", "Qty", "Unit"] + unit_cols].copy()
                
                rename_dict = {"Item_Name": "รายการสินค้า", "Qty": "จำนวน", "Unit": "หน่วยนับ"}
                for name in file_names_clean:
                    rename_dict[f"{name}_UnitPrice"] = f"{name} (ราคา/หน่วย)"
                display_unit_df.rename(columns=rename_dict, inplace=True)
                
                def highlight_min_unit(row):
                    styles = [''] * len(row)
                    p_cols = [c for c in row.index if '(ราคา/หน่วย)' in c]
                    row_prices = pd.to_numeric(row[p_cols], errors='coerce')
                    valid_prices = row_prices[row_prices > 0]
                    if not valid_prices.empty:
                        min_val = valid_prices.min()
                        for col_name in p_cols:
                            col_idx = row.index.get_loc(col_name)
                            if pd.notna(row[col_name]) and float(row[col_name]) == min_val and float(row[col_name]) > 0:
                                styles[col_idx] = 'background-color: #d4edda; color: #155724; font-weight: bold;'
                    return styles
                
                format_dict_unit = {col: "{:,.2f}" for col in display_unit_df.columns if "(ราคา/หน่วย)" in col}
                st.dataframe(display_unit_df.style.apply(highlight_min_unit, axis=1).format(format_dict_unit), use_container_width=True)
                
                # ---------------------------------------------------------
                # ส่วนแสดงผลตารางที่ 2: ตารางเปรียบเทียบยอดสุทธิ (Net Total)
                # ---------------------------------------------------------
                st.markdown("---")
                st.subheader("📊 ตารางที่ 2: เปรียบเทียบยอดสุทธิของแต่ละเจ้า (Net Total - หลังหักส่วนลดและรวม VAT)")
                
                net_cols = [f"{name}_NetTotal" for name in file_names_clean]
                display_net_df = df[["Item_Name", "Qty", "Unit"] + net_cols].copy()
                
                rename_dict_net = {"Item_Name": "รายการสินค้า", "Qty": "จำนวน", "Unit": "หน่วยนับ"}
                for name in file_names_clean:
                    rename_dict_net[f"{name}_NetTotal"] = f"{name} (สุทธิรวม VAT)"
                display_net_df.rename(columns=rename_dict_net, inplace=True)
                
                def highlight_min_net(row):
                    styles = [''] * len(row)
                    p_cols = [c for c in row.index if '(สุทธิรวม VAT)' in c]
                    row_prices = pd.to_numeric(row[p_cols], errors='coerce')
                    valid_prices = row_prices[row_prices > 0]
                    if not valid_prices.empty:
                        min_val = valid_prices.min()
                        for col_name in p_cols:
                            col_idx = row.index.get_loc(col_name)
                            if pd.notna(row[col_name]) and float(row[col_name]) == min_val and float(row[col_name]) > 0:
                                styles[col_idx] = 'background-color: #d4edda; color: #155724; font-weight: bold;'
                    return styles
                
                format_dict_net = {col: "{:,.2f}" for col in display_net_df.columns if "(สุทธิรวม VAT)" in col}
                st.dataframe(display_net_df.style.apply(highlight_min_net, axis=1).format(format_dict_net), use_container_width=True)
                
                # ---------------------------------------------------------
                # ส่วนแสดงผลตารางที่ 3: รายละเอียดเจาะลึกรายบริษัท
                # ---------------------------------------------------------
                st.markdown("---")
                st.subheader("📋 ตารางที่ 3: รายละเอียดราคาแบบเจาะลึกแยกตามผู้ขาย (รวม/ส่วนลด/หลังลด/VAT/สุทธิ)")
                
                tabs = st.tabs([f"🏢 {name}" for name in file_names_clean])
                
                for idx, name in enumerate(file_names_clean):
                    with tabs[idx]:
                        detail_cols = [
                            "Item_Name", "Qty", "Unit",
                            f"{name}_UnitPrice", f"{name}_Total", f"{name}_TotalDiscount", 
                            f"{name}_AfterDisc", f"{name}_VAT_Val", f"{name}_NetTotal"
                        ]
                        detail_df = df[detail_cols].copy()
                        detail_df.rename(columns={
                            "Item_Name": "รายการสินค้า",
                            "Qty": "จำนวน",
                            "Unit": "หน่วยนับ",
                            f"{name}_UnitPrice": "ราคา/หน่วย",
                            f"{name}_Total": "ราคารวม",
                            f"{name}_TotalDiscount": "ส่วนลด",
                            f"{name}_AfterDisc": "หลังหักส่วนลด",
                            f"{name}_VAT_Val": "VAT",
                            f"{name}_NetTotal": "ยอดสุทธิ"
                        }, inplace=True)
                        
                        format_detail = {c: "{:,.2f}" for c in ["ราคา/หน่วย", "ราคารวม", "ส่วนลด", "หลังหักส่วนลด", "VAT", "ยอดสุทธิ"]}
                        st.dataframe(detail_df.style.format(format_detail), use_container_width=True)
                        
                        sum_total = detail_df["ราคารวม"].sum()
                        sum_disc = detail_df["ส่วนลด"].sum()
                        sum_after = detail_df["หลังหักส่วนลด"].sum()
                        sum_vat = detail_df["VAT"].sum()
                        sum_net = detail_df["ยอดสุทธิ"].sum()
                        
                        st.markdown(f"""
                        **💡 สรุปยอดรวมของ {name}:**
                        - **ราคารวมก่อนลด:** {sum_total:,.2f} บาท
                        - **ส่วนลดรวม:** {sum_disc:,.2f} บาท
                        - **ราคาหลังหักส่วนลด:** {sum_after:,.2f} บาท
                        - **ภาษีมูลค่าเพิ่ม (VAT):** {sum_vat:,.2f} บาท
                        - **🔥 ยอดสุทธิต้องจ่าย (Net Total): {sum_net:,.2f} บาท**
                        """)

                # ---------------------------------------------------------
                # ส่วนแสดงผลตารางที่ 4: สรุปดีลที่ประหยัดที่สุด
                # ---------------------------------------------------------
                st.markdown("---")
                st.subheader("🏆 ตารางที่ 4: สรุปดีลที่ดีที่สุดแบบจัดเต็ม (Best Deal Summary)")
                
                summary_data = []
                total_saving_budget = 0
                
                for index, row in df.iterrows():
                    net_cols_list = [f"{name}_NetTotal" for name in file_names_clean]
                    row_net_prices = pd.to_numeric(row[net_cols_list], errors='coerce')
                    valid_net_prices = row_net_prices[row_net_prices > 0]
                    
                    if not valid_net_prices.empty:
                        min_net_val = valid_net_prices.min()
                        best_col_name = valid_net_prices.idxmin()
                        best_vendor_name = best_col_name.replace("_NetTotal", "")
                        
                        qty_val = float(row['Qty']) if pd.notna(row['Qty']) else 1
                        up_val = float(row[f"{best_vendor_name}_UnitPrice"])
                        disc_val = float(row[f"{best_vendor_name}_TotalDiscount"])
                        after_val = float(row[f"{best_vendor_name}_AfterDisc"])
                        vat_val = float(row[f"{best_vendor_name}_VAT_Val"])
                        
                        total_saving_budget += min_net_val
                        
                        summary_data.append({
                            "รายการสินค้า": row['Item_Name'],
                            "จำนวน": int(qty_val),
                            "หน่วยนับ": row['Unit'],
                            "เจ้าที่ถูกที่สุด": best_vendor_name,
                            "ราคา/หน่วย": up_val,
                            "ราคารวม": up_val * qty_val,
                            "ส่วนลด": disc_val,
                            "หลังหักส่วนลด": after_val,
                            "VAT": vat_val,
                            "ยอดสุทธิ (Min)": min_net_val
                        })
                
                summary_df = pd.DataFrame(summary_data)
                format_summary = {c: "{:,.2f}" for c in ["ราคา/หน่วย", "ราคารวม", "ส่วนลด", "หลังหักส่วนลด", "VAT", "ยอดสุทธิ (Min)"]}
                
                st.dataframe(summary_df.style.format(format_summary), use_container_width=True)
                
                st.info(f"💰 **รวมงบประมาณสุทธิเมื่อซื้อสินค้าจากเจ้าที่ถูกที่สุดในแต่ละรายการ (Best Deal Net Total): {total_saving_budget:,.2f} บาท**")
                
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาดในการประมวลผล: {e}")
            st.info("แนะนำให้ตรวจสอบว่า API Key ถูกต้อง และไฟล์ที่อัปโหลดไม่ชำรุดเสียหายครับ")
