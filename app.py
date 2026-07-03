import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os

# 1. การตั้งค่าหน้าเว็บ
st.set_page_config(layout="wide", page_title="ระบบตารางเปรียบเทียบราคาจัดซื้อ (Excel Layout)")

st.title("📊 ระบบสร้างตารางเปรียบเทียบราคาอัตโนมัติ (รูปแบบ Excel จัดซื้อ)")
st.markdown("---")
st.markdown("### 💡 วิธีใช้งาน")
st.markdown("1. ใส่ **Gemini API Key** ของคุณ")
st.markdown("2. **อัปโหลดไฟล์ใบเสนอราคา** ของเจ้าต่าง ๆ พร้อมกัน (รองรับทั้งไฟล์ **PDF, JPG, PNG**)")
st.markdown("3. ระบบจะสร้างตารางเปรียบเทียบในรูปแบบตารางเดียวจบ มีช่อง **Unit Price / Amount** แยกแต่ละเจ้า และช่อง **MIN** สรุปท้ายตาราง พร้อมแถวสรุปยอดรวมด้านล่างสุดทันที")

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
if st.button("🚀 เริ่มวิเคราะห์และสร้างตารางเปรียบเทียบ"):
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
            
            with st.spinner("⏳ AI กำลังอ่านไฟล์และจัดทำตารางเปรียบเทียบราคา โปรดรอสักครู่..."):
                
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
                
                # โครงสร้าง JSON ดึงข้อมูลพื้นฐาน ราคา หน่วยนับ และส่วนลด
                vendor_structure = ", ".join([
                    f'"{name}_UnitPrice": "ราคาต่อหน่วยก่อน VAT (ตัวเลขทศนิยม ถ้าไม่มีสินค้านี้ใส่ null, ถ้าเขียนว่า include หรือ ฟรี ให้ใส่ข้อความว่า include)", '
                    f'"{name}_DiscountStr": "ส่วนลดตามที่ระบุในบิล เช่น \'43%\', \'100\', \'0\' (ถ้าไม่มีให้ใส่ \'0\')"'
                    for name in file_names_clean
                ])
                
                prompt = f"""คุณคือผู้ช่วยฝ่ายจัดซื้อมืออาชีพที่มีความแม่นยำสูงมาก ฉันส่งไฟล์ใบเสนอราคามาให้คุณจำนวน {len(uploaded_files)} ไฟล์ ซึ่งมีชื่อไฟล์ตามลำดับดังนี้: {file_names_str}
                
หน้าที่ของคุณคือ:
1. อ่านข้อมูลรายการสินค้า จำนวน หน่วยนับ และราคาต่อหน่วย (Unit Price) จากทุกไฟล์
2. ทำการจับคู่สินค้าที่มีความหมายหรือเป็นสินค้าชนิดเดียวกัน ให้อยู่ในแถว (Row) เดียวกัน
3. ดึงราคาต่อหน่วยที่เป็นราคา "ก่อน VAT" หากมีส่วนลดให้ระบุข้อความส่วนลดมาด้วย (เช่น "43%")
4. กรณีค่าใช้จ่ายพิเศษ เช่น ค่าขนส่ง (Freight / Transportation) ถ้าในใบเสนอราคาเขียนว่า "include", "รวมแล้ว", หรือ "ฟรี" ให้ใส่ค่าใน UnitPrice เป็นข้อความว่า "include" แต่ถ้ามีราคาให้ใส่ตัวเลขตามปกติ
5. ส่งคืนข้อมูลเป็นรูปแบบ JSON Array ของ Object เท่านั้น ห้ามมีข้อความอื่น โดยใช้โครงสร้างคีย์ดังนี้:
[
  {{
    "Item_Name": "ชื่อรายการสินค้าหรือค่าบริการ",
    "Qty": จำนวน (ตัวเลขเท่านั้น),
    "Unit": "หน่วยนับ (เช่น set, pcs, JOB, EA, ม.),",
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
                
                # 4. ประมวลผลราคาหลังหักส่วนลด และคำนวณ Amount (Qty * UnitPrice)
                qty_series = pd.to_numeric(df['Qty'], errors='coerce').fillna(1)
                
                vendor_unit_prices = {}
                vendor_amounts = {}
                
                for name in file_names_clean:
                    u_col = f"{name}_UnitPrice"
                    d_col = f"{name}_DiscountStr"
                    
                    final_u_list = []
                    amount_list = []
                    
                    for i, row in df.iterrows():
                        u_val_raw = str(row.get(u_col, '')).strip()
                        qty_val = qty_series.iloc[i]
                        
                        if 'include' in u_val_raw.lower() or 'รวม' in u_val_raw or 'ฟรี' in u_val_raw or 'free' in u_val_raw.lower():
                            final_u_list.append("include")
                            amount_list.append("include")
                        elif u_val_raw == 'None' or u_val_raw == 'null' or u_val_raw == '' or u_val_raw == '-':
                            final_u_list.append("-")
                            amount_list.append("-")
                        else:
                            u_num = pd.to_numeric(u_val_raw, errors='coerce')
                            if pd.isna(u_num):
                                final_u_list.append("-")
                                amount_list.append("-")
                            else:
                                disc_str = str(row.get(d_col, '0')).strip()
                                if '%' in disc_str:
                                    pct = pd.to_numeric(disc_str.replace('%', ''), errors='coerce') or 0
                                    u_num = u_num * (1 - pct/100.0)
                                elif disc_str != '0' and disc_str != '-' and disc_str != '':
                                    disc_num = pd.to_numeric(disc_str, errors='coerce') or 0
                                    u_num = max(0, u_num - disc_num)
                                
                                amt_num = u_num * qty_val
                                final_u_list.append(u_num)
                                amount_list.append(amt_num)
                    
                    vendor_unit_prices[name] = final_u_list
                    vendor_amounts[name] = amount_list
                
                # 5. คำนวณหาช่อง MIN (Unit Price และ Amount)
                min_unit_list = []
                min_amount_list = []
                
                for i in range(len(df)):
                    row_prices = []
                    for name in file_names_clean:
                        val = vendor_unit_prices[name][i]
                        if isinstance(val, (int, float)):
                            row_prices.append(val)
                    
                    if len(row_prices) > 0:
                        min_p = min(row_prices)
                        min_unit_list.append(min_p)
                        min_amount_list.append(min_p * qty_series.iloc[i])
                    else:
                        has_include = any(vendor_unit_prices[name][i] == "include" for name in file_names_clean)
                        if has_include:
                            min_unit_list.append("include")
                            min_amount_list.append("include")
                        else:
                            min_unit_list.append("-")
                            min_amount_list.append("-")
                
                # 6. สร้างตารางแบบ Layout Excel
                table_data = {}
                table_data["ลำดับ"] = list(range(1, len(df) + 1))
                table_data["รายการ"] = df["Item_Name"]
                table_data["ขนาด"] = qty_series.astype(int)
                table_data["หน่วย"] = df["Unit"]
                
                for name in file_names_clean:
                    table_data[f"{name} | Unit Price"] = vendor_unit_prices[name]
                    table_data[f"{name} | Amount"] = vendor_amounts[name]
                
                table_data["⭐ MIN | Unit Price"] = min_unit_list
                table_data["⭐ MIN | Amount"] = min_amount_list
                
                result_df = pd.DataFrame(table_data)
                
                # 7. เพิ่มแถวสรุปท้ายตาราง (ราคารวม, Vat.7%, ราคารวมภาษี)
                sum_row = {"ลำดับ": "", "รายการ": "ราคารวม (Total)", "ขนาด": "", "หน่วย": ""}
                vat_row = {"ลำดับ": "", "รายการ": "Vat. 7%", "ขนาด": "", "หน่วย": ""}
                net_row = {"ลำดับ": "", "รายการ": "ราคารวมภาษี (Net Total)", "ขนาด": "", "หน่วย": ""}
                
                all_sections = file_names_clean + ["⭐ MIN"]
                
                for sec in all_sections:
                    amt_col = f"{sec} | Amount"
                    u_col = f"{sec} | Unit Price"
                    
                    numeric_amounts = [val for val in table_data[amt_col] if isinstance(val, (int, float))]
                    total_amt = sum(numeric_amounts)
                    vat_amt = total_amt * 0.07
                    net_amt = total_amt + vat_amt
                    
                    sum_row[u_col] = ""
                    sum_row[amt_col] = total_amt
                    
                    vat_row[u_col] = ""
                    vat_row[amt_col] = vat_amt
                    
                    net_row[u_col] = ""
                    net_row[amt_col] = net_amt
                
                summary_df = pd.DataFrame([sum_row, vat_row, net_row])
                final_display_df = pd.concat([result_df, summary_df], ignore_index=True)
                
                # 8. ฟังก์ชันตกแต่งสี (Highlight)
                def style_excel_layout(df_in):
                    styles = pd.DataFrame('', index=df_in.index, columns=df_in.columns)
                    
                    for col in df_in.columns:
                        if "MIN" in col:
                            styles[col] = 'background-color: #e2efda; font-weight: bold;'
                    
                    for r_idx in range(len(df_in) - 3, len(df_in)):
                        styles.iloc[r_idx, :] = 'background-color: #f2f2f2; font-weight: bold;'
                        if "MIN" in styles.columns[0]:
                            for col in df_in.columns:
                                if "MIN" in col:
                                    styles.iloc[r_idx][col] = 'background-color: #c6e0b4; font-weight: bold; color: #006100;'
                    
                    for r_idx in range(len(df_in) - 3):
                        min_val = df_in.loc[r_idx, "⭐ MIN | Unit Price"]
                        if isinstance(min_val, (int, float)):
                            for name in file_names_clean:
                                u_col = f"{name} | Unit Price"
                                amt_col = f"{name} | Amount"
                                val = df_in.loc[r_idx, u_col]
                                if isinstance(val, (int, float)) and val == min_val:
                                    styles.loc[r_idx, u_col] = 'background-color: #c6e0b4; color: #006100; font-weight: bold;'
                                    styles.loc[r_idx, amt_col] = 'background-color: #c6e0b4; color: #006100; font-weight: bold;'
                                    
                    return styles

                def format_cell(val):
                    if isinstance(val, (int, float)):
                        return f"{val:,.2f}"
                    return str(val) if val is not None else ""

                st.success("✅ สร้างตารางเปรียบเทียบรูปแบบ Excel สำเร็จ!")
                st.markdown("### 📋 ตารางเปรียบเทียบราคา (สามารถคัดลอกลง Excel ได้ทันที)")
                
                formatted_df = final_display_df.copy()
                for col in formatted_df.columns:
                    if "Unit Price" in col or "Amount" in col:
                        formatted_df[col] = formatted_df[col].apply(format_cell)
                        
                st.dataframe(
                    formatted_df.style.apply(style_excel_layout, axis=None), 
                    use_container_width=True,
                    height=500
                )
                
                best_deal_total = final_display_df.loc[len(final_display_df)-1, "⭐ MIN | Amount"]
                st.info(f"💰 **ยอดงบประมาณจัดซื้อที่ประหยัดที่สุด (MIN Net Total รวม VAT 7%): {best_deal_total:,.2f} บาท**")
                
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาดในการประมวลผล: {e}")
            st.info("แนะนำให้ตรวจสอบว่า API Key ถูกต้อง และไฟล์ที่อัปโหลดไม่ชำรุดเสียหายครับ")
