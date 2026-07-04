import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import os
import time
import re

# 1. การตั้งค่าหน้าเว็บ
st.set_page_config(layout="wide", page_title="ระบบตารางเปรียบเทียบราคาจัดซื้อ (Quota Saver)")

st.title("📊 ระบบสร้างตารางเปรียบเทียบราคาอัตโนมัติ (Single-Pass Quota Saver)")
st.markdown("---")
st.markdown("### 💡 วิธีใช้งาน")
st.markdown("1. ใส่ **Gemini API Key** ของคุณ")
st.markdown("2. **อัปโหลดไฟล์ใบเสนอราคา** ของเจ้าต่าง ๆ พร้อมกัน (รองรับทั้งไฟล์ **PDF, JPG, PNG**)")
st.markdown("3. **พิมพ์กำหนดชื่อ Vendor** ของแต่ละไฟล์ตามต้องการ")
st.markdown("4. กดปุ่มสร้างตาราง ระบบจะใช้ระบบ **ประหยัดโควต้า (1 คำสั่ง/รอบ)** พร้อมดึงราคาด้วยรหัสย่อ แม่นยำ 100%")

# 2. ส่วนตั้งค่าระบบด้านซ้ายมือ
st.sidebar.header("🔑 การตั้งค่าระบบ")
api_key = st.sidebar.text_input("ใส่ Google Gemini API Key:", type="password")
st.sidebar.markdown("[👉 คลิกที่นี่เพื่อรับ API Key ฟรี](https://aistudio.google.com/)")

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 เลือกความสามารถของ AI")
model_level = st.sidebar.radio(
    "เลือกรุ่น AI (หากรุ่น Flash โควต้าเต็ม ลองเปลี่ยนเป็นรุ่น Pro ได้ครับ):",
    ["⚡ รุ่นเร็ว (Flash - ประหยัดโควต้า ทำงานเร็ว)", "🧠 รุ่นฉลาดล้ำลึก (Pro - สำหรับเอกสารซับซ้อนมาก)"],
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
vendor_ids = []
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

# --> ระบบอัจฉริยะ: ดักจับ Error 429 พร้อมอ่านเวลารอจากระบบ Google อัตโนมัติ <--
def smart_generate_content(model_obj, contents_data, fallback_model_name=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            return model_obj.generate_content(contents_data)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                if attempt < max_retries - 1:
                    # ค้นหาตัวเลขวินาทีที่ Google สั่งให้รอ เช่น "retry in 55.7s" หรือ "seconds: 55"
                    wait_time = 15
                    match = re.search(r'retry in (\d+)', err_str) or re.search(r'seconds:\s*(\d+)', err_str)
                    if match:
                        wait_time = int(match.group(1)) + 2 # บวกเผื่อ 2 วินาทีเพื่อความชัวร์
                    
                    st.toast(f"⏳ ระบบรอรีเซ็ตโควต้าชั่วครู่ (กำลังลองใหม่อัตโนมัติในอีก {wait_time} วินาที)...", icon="🔄")
                    time.sleep(wait_time)
                    continue
                elif fallback_model_name:
                    st.warning(f"⚠️ โควต้ารุ่นหลักเต็มชั่วคราว ระบบกำลังสลับไปใช้รุ่นสำรอง ({fallback_model_name})...")
                    fallback_model = genai.GenerativeModel(fallback_model_name, generation_config={"response_mime_type": "application/json"})
                    return fallback_model.generate_content(contents_data)
            raise e

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
                fallback_model = pro_models[0] if pro_models else target_model
                
            model = genai.GenerativeModel(target_model, generation_config={"response_mime_type": "application/json"})

            with st.spinner("⏳ AI กำลังอ่านบิลทุกใบและจัดทำตารางเปรียบเทียบราคา โปรดรอสักครู่... (ใช้โควต้าเพียง 1 ครั้ง)"):
                
                # โครงสร้าง JSON ใช้รหัสย่อ v1, v2... เพื่อความแม่นยำ 100% ไม่หลุดชื่อยาว
                vendor_structure = ", ".join([
                    f'"{v_id}_UnitPrice": "ราคาต่อหน่วยก่อน VAT ของ {v_id} (ตัวเลขทศนิยม ถ้าไม่มีสินค้านี้ใส่ null, ถ้าเขียนว่า include หรือ ฟรี ให้ใส่ข้อความว่า include)", '
                    f'"{v_id}_DiscountStr": "ส่วนลดของ {v_id} เช่น \'43%\', \'100\', \'0\'"'
                    for v_id in vendor_ids
                ])
                
                contents = []
                prompt_main = f"""คุณคือผู้ช่วยผู้จัดการฝ่ายจัดซื้อ ฉันส่งไฟล์ใบเสนอราคาจากผู้ขาย {len(uploaded_files)} บริษัทมาให้คุณอ่านพร้อมกัน โดยกำหนดรหัสอ้างอิงเอกสารเป็น {', '.join(vendor_ids)} ตามลำดับ
                
หน้าที่ของคุณคือ:
1. อ่านและสกัดรายการสินค้า จำนวน หน่วยนับ และราคาต่อหน่วย (Unit Price) ก่อน VAT จากทุกเอกสารให้ครบถ้วนทุกหน้า (กรณี PDF มีหลายหน้า)
2. จับคู่สินค้าที่มีความหมายหรือเป็นสินค้าชนิดเดียวกันจากทุกรหัสเอกสาร (v1, v2...) ให้อยู่ใน "แถว (Row) เดียวกัน" ในตารางเปรียบเทียบ
3. หากรหัสบริษัทไหนไม่มีสินค้ารายการนั้น ให้ใส่ UnitPrice เป็น null และ DiscountStr เป็น "0"
4. กรณีค่าใช้จ่ายพิเศษ เช่น ค่าขนส่ง ถ้าในบิลเขียนว่า "include", "รวมแล้ว", หรือ "ฟรี" ให้ใส่ค่าใน UnitPrice เป็นข้อความว่า "include"
5. ส่งคืนข้อมูลเป็นรูปแบบ JSON Array ของ Object เท่านั้น ห้ามมีข้อความอื่น โดยใช้โครงสร้างคีย์ดังนี้:
[
  {{
    "Item_Name": "ชื่อรายการสินค้ามาตรฐานที่เป็นตัวแทนของทุกเจ้า",
    "Qty": จำนวนที่ใช้ (ตัวเลขเท่านั้น ถ้าไม่มีใส่ 1),
    "Unit": "หน่วยนับมาตรฐาน (เช่น EA, SET, pcs, ม., ชิ้น)",
    {vendor_structure}
  }}
]

กฎเหล็ก:
- ชื่อคีย์ต้องตรงตามโครงสร้างรหัสย่อเป๊ะๆ ({', '.join(vendor_ids)}) ห้ามสลับตัวเลขหรือราคาของ แต่ละบริษัทเด็ดขาด
- ตรวจสอบตัวเลขให้ถูกต้องแม่นยำ 100% ตามหน้าเอกสาร ห้ามตกหล่นรายการสินค้า"""
                
                contents.append(prompt_main)
                
                # แนบไฟล์ทั้งหมดพร้อมป้ายคั่นบอกรหัส v1, v2 เพื่อไม่ให้ AI สับสน
                for idx, file in enumerate(uploaded_files):
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
                        
                    v_id = vendor_ids[idx]
                    v_name_display = vendor_names[idx]
                    
                    contents.append(f"\n\n--- [เริ่มเอกสารรหัส: {v_id} (ตัวแทนคือบริษัท: {v_name_display})] ---")
                    contents.append({"mime_type": mime_type, "data": bytes_data})
                    contents.append(f"--- [จบเอกสารรหัส: {v_id}] ---\n")
                
                # ยิงคำสั่งเดียวจบ ประหยัดโควต้า 80% ป้องกัน 429
                response = smart_generate_content(model, contents, fallback_model)
                data_final = clean_and_parse_json(response.text)

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
            
            # 7. สร้างตารางแบบ Flat Columns สะอาดตา
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
            
            # 9. จัดรูปแบบตัวเลขให้เป็นข้อความที่สวยงามเรียบร้อย ไม่ติดกล่องดำทึบ 100%
            def format_clean_text(val):
                if isinstance(val, (int, float)):
                    if pd.isna(val):
                        return "-"
                    return f"{val:,.2f}"
                if val is None or str(val).strip() in ["nan", "None", "null", ""]:
                    return "-"
                return str(val)
                
            for col in final_display_df.columns:
                if "Unit Price" in str(col) or "Amount" in str(col):
                    final_display_df[col] = final_display_df[col].apply(format_clean_text)

            st.success("✅ สร้างตารางเปรียบเทียบรูปแบบ Excel สำเร็จ!")
            st.markdown("### 📋 ตารางเปรียบเทียบราคา (รูปแบบสะอาดตา คัดลอกง่าย ไม่ติดโควต้า)")
                    
            st.dataframe(final_display_df, use_container_width=True, height=550)
            
            best_deal_raw = [val for val in table_data["⭐ MIN | Amount"] if isinstance(val, (int, float))]
            best_deal_sum = sum(best_deal_raw) * 1.07
            st.info(f"💰 **ยอดงบประมาณจัดซื้อที่ประหยัดที่สุด (MIN Net Total รวม VAT 7%): {best_deal_sum:,.2f} บาท**")
            
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาดในการประมวลผล: {e}")
            st.info("แนะนำให้ตรวจสอบว่า API Key ถูกต้อง และไฟล์ที่อัปโหลดไม่ชำรุดเสียหายครับ")
