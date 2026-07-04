import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os

# 1. การตั้งค่าหน้าเว็บ
st.set_page_config(layout="wide", page_title="ระบบตารางเปรียบเทียบราคาจัดซื้อ (Two-Stage Engine)")

st.title("📊 ระบบสร้างตารางเปรียบเทียบราคาอัตโนมัติ (Two-Stage AI Engine)")
st.markdown("---")
st.markdown("### 💡 วิธีใช้งาน")
st.markdown("1. ใส่ **Gemini API Key** ของคุณ")
st.markdown("2. **อัปโหลดไฟล์ใบเสนอราคา** ของเจ้าต่าง ๆ พร้อมกัน (รองรับทั้งไฟล์ **PDF, JPG, PNG**)")
st.markdown("3. **พิมพ์กำหนดชื่อ Vendor** ของแต่ละไฟล์ตามต้องการ (ตั้งชื่อยาว มีวงเล็บ หรือภาษาไทยได้สบายครับ)")
st.markdown("4. กดปุ่มสร้างตาราง ระบบจะ **อ่านแยกทีละบิลเพื่อความแม่นยำ 100%** แล้วค่อยนำมารวมตารางเปรียบเทียบให้ทันที")

# 2. ส่วนตั้งค่าระบบด้านซ้ายมือ
st.sidebar.header("🔑 การตั้งค่าระบบ")
api_key = st.sidebar.text_input("ใส่ Google Gemini API Key:", type="password")
st.sidebar.markdown("[👉 คลิกที่นี่เพื่อรับ API Key ฟรี](https://aistudio.google.com/)")

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 เลือกความสามารถของ AI")
model_level = st.sidebar.radio(
    "เลือกรุ่น AI (หากรุ่น Pro โควต้าเต็ม ระบบจะเปลี่ยนเป็น Flash ให้อัตโนมัติ):",
    ["⚡ รุ่นเร็ว (Flash - โควต้าฟรีเยอะมาก อ่านบิลเร็ว)", "🧠 รุ่นฉลาดล้ำลึก (Pro - สำหรับเอกสารซับซ้อนมาก)"],
    index=0
)

st.markdown("---")
st.subheader("📁 1. อัปโหลดเอกสารใบเสนอราคา")
uploaded_files = st.file_uploader(
    "เลือกไฟล์ใบเสนอราคา (เลือกพร้อมกันหลายไฟล์ได้)", 
    accept_multiple_files=True, 
    type=['pdf', 'png', 'jpg', 'jpeg']
)

# 3. ส่วนตั้งชื่อ Vendor
vendor_names = []
vendor_ids = [] # รหัสย่อ v1, v2, v3...
if uploaded_files:
    st.markdown("### 🏷️ 2. กำหนดชื่อบริษัทผู้ขาย (Vendor Names)")
    st.caption("💡 ระบบดึงชื่อจากไฟล์มาเป็นค่าเริ่มต้นให้ คุณสามารถพิมพ์แก้ไขเป็นชื่อเต็ม ชื่อย่อ หรือมีวงเล็บได้เลยครับ")
    
    cols = st.columns(len(uploaded_files))
    for idx, file in enumerate(uploaded_files):
        default_name = os.path.splitext(file.name)[0]
        v_id = f"v{idx+1}"
        vendor_ids.append(v_id)
        with cols[idx]:
            v_name = st.text_input(f"🏢 เจ้าที่ {idx+1} (รหัส {v_id}):", value=default_name, key=f"vendor_{idx}")
            clean_v_name = v_name.strip() if v_name.strip() else f"Vendor_{idx+1}"
            vendor_names.append(clean_v_name)

st.markdown("---")

# ฟังก์ชันดักจับ Error แปลง JSON
def clean_and_parse_json(text):
    try:
        return json.loads(text)
    except:
        clean_text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)

# 4. เริ่มประมวลผลเมื่อกดปุ่ม
if st.button("🚀 3. เริ่มวิเคราะห์และสร้างตารางเปรียบเทียบ") and uploaded_files:
    if not api_key:
        st.error("❌ กรุณาใส่ Gemini API Key ในแถบด้านซ้ายก่อนเริ่มใช้งาน")
    else:
        try:
            genai.configure(api_key=api_key)
            
            valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            flash_models = [m for m in valid_models if 'flash' in m.lower()]
            pro_models = [m for m in valid_models if 'pro' in m.lower()]
            
            if ("Pro" in model_level or "pro" in model_level) and pro_models:
                target_model = pro_models[0]
                fallback_model = flash_models[0] if flash_models else valid_models[0]
            else:
                target_model = flash_models[0] if flash_models else valid_models[0]
                fallback_model = target_model
                
            # สร้าง Model
            try:
                model = genai.GenerativeModel(target_model, generation_config={"response_mime_type": "application/json"})
                # ทดสอบเรียกเบาๆ เพื่อเช็คโควต้า
                model.generate_content("test")
            except Exception as api_err:
                if "429" in str(api_err) or "quota" in str(api_err).lower() or "404" in str(api_err):
                    st.warning(f"⚠️ โควต้าฟรีของรุ่น Pro เต็ม ระบบกำลังสลับไปใช้รุ่น Flash ({fallback_model}) ให้อัตโนมัติครับ...")
                    model = genai.GenerativeModel(fallback_model, generation_config={"response_mime_type": "application/json"})
                else:
                    model = genai.GenerativeModel(fallback_model, generation_config={"response_mime_type": "application/json"})

            # --> เริ่มต้นการทำงานแบบ TWO-STAGE ENGINE <--
            with st.status("🚀 กำลังประมวลผลระบบจัดซื้ออัตโนมัติ (Two-Stage Engine)...", expanded=True) as status:
                
                # ==========================================
                # STAGE 1: อ่านแยกทีละบิล (100% Accuracy)
                # ==========================================
                extracted_data = {}
                
                for idx, file in enumerate(uploaded_files):
                    v_id = vendor_ids[idx]
                    v_name = vendor_names[idx]
                    status.write(f"📄 **ขั้นที่ 1 ({idx+1}/{len(uploaded_files)}):** กำลังอ่านและดึงตัวเลขจากใบเสนอราคาของ **{v_name}**...")
                    
                    bytes_data = file.read()
                    file_ext = os.path.splitext(file.name)[1].lower()
                    if file_ext == '.pdf':
                        mime_type = 'application/pdf'
                    elif file_ext in ['.jpg', '.jpeg']:
                        mime_type = 'image/jpeg'
                    elif file_ext == '.png':
                        mime_type = 'image/png'
                    else:
                        mime_type = file.type or 'application/octet-stream'
                        
                    prompt_stage1 = f"""คุณคือผู้ช่วยฝ่ายจัดซื้อ จงอ่านเอกสารใบเสนอราคานี้อย่างละเอียดทุกหน้า แล้วดึงรายการสินค้าทุกรายการออกมาเป็น JSON Array
                    โดยแต่ละรายการต้องมีโครงสร้างดังนี้:
                    [
                      {{
                        "Item_Name": "ชื่อรายการสินค้า ขนาด หรือรุ่น",
                        "Qty": จำนวนสินค้า (ตัวเลขเท่านั้น ถ้าไม่มีให้ใส่ 1),
                        "Unit": "หน่วยนับ (เช่น EA, SET, pcs, ม., ชิ้น)",
                        "UnitPrice": ราคาต่อหน่วยก่อน VAT (ตัวเลขทศนิยมเท่านั้น ห้ามใส่เครื่องหมายคอมม่า (,) ถ้าเขียนว่า include, ฟรี หรือ รวมแล้ว ให้ใส่ข้อความว่า 'include')",
                        "DiscountStr": "ส่วนลดของรายการนี้ เช่น '43%', '100', '0' (ถ้าไม่มีให้ใส่ '0')"
                      }}
                    ]
                    ห้ามตกหล่นรายการสินค้าเด็ดขาด ต้องดึงมาให้ครบทุกข้อตามใบเสนอราคา"""
                    
                    res_stage1 = model.generate_content([prompt_stage1, {"mime_type": mime_type, "data": bytes_data}])
                    extracted_data[v_id] = clean_and_parse_json(res_stage1.text)
                
                # ==========================================
                # STAGE 2: จับคู่รายการเข้าตารางเปรียบเทียบ
                # ==========================================
                status.write("🧩 **ขั้นที่ 2:** ดึงราคาครบทุกเจ้าแล้ว! กำลังวิเคราะห์และจับคู่สินค้าให้อยู่บรรทัดเดียวกัน...")
                
                vendor_structure = ", ".join([
                    f'"{v_id}_UnitPrice": "ราคาต่อหน่วยก่อน VAT ของ {v_id} (ตัวเลข หรือ คำว่า include หรือ null)", '
                    f'"{v_id}_DiscountStr": "ส่วนลดของ {v_id} เช่น \'43%\', \'100\', \'0\'"'
                    for v_id in vendor_ids
                ])
                
                prompt_stage2 = f"""คุณคือผู้ช่วยผู้จัดการฝ่ายจัดซื้อ ฉันมีข้อมูลรายการสินค้าที่สกัดมาจากใบเสนอราคาของ {len(vendor_ids)} บริษัท โดยใช้รหัสอ้างอิงคือ {', '.join(vendor_ids)} ดังนี้:
                {json.dumps(extracted_data, ensure_ascii=False, indent=2)}
                
                หน้าที่ของคุณคือ:
                1. นำรายการสินค้าจากทุกรหัสบริษัท (v1, v2...) มาจับคู่กันให้อยู่ใน "แถว (Row) เดียวกัน" หากเป็นสินค้าชนิดเดียวกัน หรือขนาด/คุณสมบัติเดียวกัน (แม้อาจเขียนชื่อต่างกันเล็กน้อย)
                2. หากรหัสบริษัทไหนไม่มีสินค้ารายการนั้น ให้ใส่ UnitPrice เป็น null และ DiscountStr เป็น "0"
                3. ส่งคืนเป็น JSON Array ของ Object เท่านั้น โดยต้องมีโครงสร้างคีย์ดังนี้:
                [
                  {{
                    "Item_Name": "ชื่อรายการสินค้ามาตรฐานที่เป็นตัวแทนของทุกเจ้า",
                    "Qty": จำนวนที่ใช้ (ตัวเลข),
                    "Unit": "หน่วยนับมาตรฐาน",
                    {vendor_structure}
                  }}
                ]
                
                กฎเหล็ก:
                - ชื่อคีย์ต้องตรงตามโครงสร้างรหัสย่อเป๊ะๆ ({', '.join(vendor_ids)}) ห้ามสลับตัวเลขหรือราคาของแต่ละบริษัทเด็ดขาด
                - ตรวจสอบความถูกต้องของตัวเลขราคาและส่วนลด ให้ตรงกับข้อมูลที่ส่งไป 100% ห้ามตกหล่น"""
                
                res_stage2 = model.generate_content(prompt_stage2)
                data_final = clean_and_parse_json(res_stage2.text)
                
                status.update(label="✅ อ่านข้อมูลและสร้างตารางเปรียบเทียบสำเร็จเรียบร้อย!", state="complete", expanded=False)

            df = pd.DataFrame(data_final)
            
            # 5. ประมวลผลราคาหลังหักส่วนลด และคำนวณ Amount
            qty_series = pd.to_numeric(df['Qty'], errors='coerce').fillna(1)
            
            vendor_unit_prices = {}
            vendor_amounts = {}
            
            for idx, v_id in enumerate(vendor_ids):
                u_col = f"{v_id}_UnitPrice"
                d_col = f"{v_id}_DiscountStr"
                
                final_u_list = []
                amount_list = []
                
                for i, row in df.iterrows():
                    u_val_raw = str(row.get(u_col, '')).strip()
                    qty_val = qty_series.iloc[i]
                    
                    if not u_val_raw or u_val_raw.lower() in ['none', 'null', '', '-', 'nan', 'empty']:
                        final_u_list.append("-")
                        amount_list.append("-")
                    elif 'include' in u_val_raw.lower() or 'รวม' in u_val_raw or 'ฟรี' in u_val_raw or 'free' in u_val_raw.lower():
                        final_u_list.append("include")
                        amount_list.append("include")
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
                
                display_name = vendor_names[idx]
                vendor_unit_prices[display_name] = final_u_list
                vendor_amounts[display_name] = amount_list
            
            # 6. คำนวณหาช่อง MIN
            min_unit_list = []
            min_amount_list = []
            
            for i in range(len(df)):
                row_prices = []
                for name in vendor_names:
                    val = vendor_unit_prices[name][i]
                    if isinstance(val, (int, float)):
                        row_prices.append(val)
                
                if len(row_prices) > 0:
                    min_p = min(row_prices)
                    min_unit_list.append(min_p)
                    min_amount_list.append(min_p * qty_series.iloc[i])
                else:
                    has_include = any(vendor_unit_prices[name][i] == "include" for name in vendor_names)
                    if has_include:
                        min_unit_list.append("include")
                        min_amount_list.append("include")
                    else:
                        min_unit_list.append("-")
                        min_amount_list.append("-")
            
            # 7. สร้างตาราง
            table_data = {}
            table_data['ลำดับ'] = list(range(1, len(df) + 1))
            table_data['รายการ'] = df["Item_Name"]
            table_data['ขนาด'] = qty_series.astype(int)
            table_data['หน่วย'] = df["Unit"]
            
            for name in vendor_names:
                table_data[f"{name} | Unit Price"] = vendor_unit_prices[name]
                table_data[f"{name} | Amount"] = vendor_amounts[name]
            
            table_data["⭐ MIN | Unit Price"] = min_unit_list
            table_data["⭐ MIN | Amount"] = min_amount_list
            
            result_df = pd.DataFrame(table_data)
            
            # 8. เพิ่มแถวสรุปท้ายตาราง
            sum_row = {'ลำดับ': "", 'รายการ': "ราคารวม (Total)", 'ขนาด': "", 'หน่วย': ""}
            vat_row = {'ลำดับ': "", 'รายการ': "Vat. 7%", 'ขนาด': "", 'หน่วย': ""}
            net_row = {'ลำดับ': "", 'รายการ': "ราคารวมภาษี (Net Total)", 'ขนาด': "", 'หน่วย': ""}
            
            all_sections = vendor_names + ["⭐ MIN"]
            
            for sec in all_sections:
                u_col = f"{sec} | Unit Price"
                amt_col = f"{sec} | Amount"
                
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
            
            # 9. ฟังก์ชันไฮไลท์สีเขียว
            def clean_style(df_in):
                styles = pd.DataFrame('', index=df_in.index, columns=df_in.columns)
                
                for col in df_in.columns:
                    if "MIN" in col:
                        styles[col] = 'background-color: rgba(198, 224, 180, 0.25);'
                
                for r_idx in range(len(df_in) - 3):
                    min_val = df_in.loc[r_idx, "⭐ MIN | Unit Price"]
                    if isinstance(min_val, (int, float)) and min_val > 0:
                        for name in vendor_names:
                            u_col = f"{name} | Unit Price"
                            amt_col = f"{name} | Amount"
                            val = df_in.loc[r_idx, u_col]
                            if isinstance(val, (int, float)) and abs(val - min_val) < 1e-4:
                                styles.loc[r_idx, u_col] = 'background-color: #c6e0b4 !important; color: #006100 !important; font-weight: bold;'
                                styles.loc[r_idx, amt_col] = 'background-color: #c6e0b4 !important; color: #006100 !important; font-weight: bold;'
                
                for r_idx in range(len(df_in) - 3, len(df_in)):
                    styles.iloc[r_idx, :] = 'background-color: rgba(128, 128, 128, 0.2) !important; font-weight: bold;'
                    for col in df_in.columns:
                        if "MIN" in col:
                            styles.loc[r_idx, col] = 'background-color: #a9d08e !important; color: #000000 !important; font-weight: bold;'
                            
                return styles

            st.success("✅ สร้างตารางเปรียบเทียบรูปแบบ Excel สำเร็จ!")
            st.markdown("### 📋 ตารางเปรียบเทียบราคา (ไฮไลท์สีเขียวเจ้าที่ถูกสุด)")
            
            format_dict = {}
            for col in final_display_df.columns:
                if "Unit Price" in col or "Amount" in col:
                    format_dict[col] = lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) else str(x if x is not None else "")
                    
            styler = final_display_df.style.apply(clean_style, axis=None).format(format_dict)
                    
            st.dataframe(styler, use_container_width=True, height=550)
            
            best_deal_total = final_display_df.loc[len(final_display_df)-1, "⭐ MIN | Amount"]
            st.info(f"💰 **ยอดงบประมาณจัดซื้อที่ประหยัดที่สุด (MIN Net Total รวม VAT 7%): {best_deal_total:,.2f} บาท**")
            
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาดในการประมวลผล: {e}")
            st.info("แนะนำให้ตรวจสอบว่า API Key ถูกต้อง และไฟล์ที่อัปโหลดไม่ชำรุดเสียหายครับ")
