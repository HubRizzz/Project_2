import os
import streamlit as st
from google import genai
from google.genai.errors import APIError
from PIL import Image
import io
from datetime import datetime

# KHAI BÁO CÁC KHÓA API VÀ THAY THẾ KHỞI TẠO CLIENT CŨ
API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3")
]
# Lọc bỏ các giá trị rỗng hoặc None
VALID_API_KEYS = [key for key in API_KEYS if key]

# Đặt biến client để đảm bảo các dòng code khác không bị lỗi Reference
client = True # Giả định luôn có client để code chính chạy

# --- HÀM MỚI: GỌI API VỚI LOGIC FAILOVER (IM LẶNG) ---
def safe_generate_content(model, contents):
    """Thử từng Khóa API trong danh sách cho đến khi thành công hoặc hết."""
    
    if not VALID_API_KEYS:
        # Nếu không có Khóa API hợp lệ, raise lỗi API giả (giống lỗi 429)
        raise APIError("429 RESOURCE_EXHAUSTED. All keys failed.")

    for i, api_key in enumerate(VALID_API_KEYS):
        try:
            # Khởi tạo Client MỚI cho mỗi lần thử để đảm bảo dùng Khóa đúng
            temp_client = genai.Client(api_key=api_key)
            
            # Thực hiện cuộc gọi API
            response = temp_client.models.generate_content(
                model=model, 
                contents=contents
            )
            
            # Nếu thành công, trả về phản hồi ngay lập tức
            return response
            
        except APIError as e:
            error_str = str(e)
            
            # Nếu là lỗi 429 hoặc lỗi khác, CẦN TIẾP TỤC mà KHÔNG THÔNG BÁO
            # để thử Khóa API tiếp theo
            if "429" in error_str or "PERMISSION_DENIED" in error_str or "403" in error_str:
                continue 
            
            # Nếu là lỗi API khác (ví dụ: mô hình không tồn tại), báo lỗi và thoát
            raise e 
        
    # Nếu tất cả các Khóa API đều thất bại do 429 hoặc 403, 
    # TA PHẢI RAISE MỘT LỖI CÓ CHỨA '429' (Giả lập hết hạn mức ngày)
    raise APIError("429 RESOURCE_EXHAUSTED: All keys failed due to quota.")
# -----------------------------------------------------------------


# --- PROMPT CỐ ĐỊNH CỦA HỆ THỐNG (SYSTEM INSTRUCTION) ---
SYSTEM_INSTRUCTION = ("""
Bạn là một chuyên gia về môi trường và phân loại rác thải.

Nhiệm vụ của bạn:
1. Xác định loại rác: Tái chế, Hữu cơ, hoặc Vô cơ/Khác.
2. Giải thích rõ ràng vì sao rác này thuộc loại đó.
3. Hướng dẫn cách xử lý phù hợp để bảo vệ môi trường.
4. Cung cấp thêm ít nhất 1 thông tin hoặc fact liên quan đến ô nhiễm, môi trường hoặc tái chế.
5. Trình bày câu trả lời thành một đoạn văn hoàn chỉnh, dễ hiểu, giống văn phong thuyết trình học tập.

Nếu người dùng không cung cấp đủ thông tin (không có ảnh và không có mô tả),
hãy lịch sự yêu cầu họ cung cấp thêm thông tin.

KHÔNG trả lời quá ngắn.
"""
)
# -----------------------------------------------------------------

# --- KHỞI TẠO BỘ NHỚ LỊCH SỬ ---
if 'history' not in st.session_state:
    st.session_state.history = []

# ✅ BƯỚC 3 — THÊM DỮ LIỆU MẪU (ĐỂ DEMO)
sample_data = [
    {"response": "rác tái chế"},
    {"response": "chai nhựa nên vào thùng tái chế"},
    {"response": "vỏ chuối là hữu cơ"},
    {"response": "rác hữu cơ"},
    {"response": "pin là rác vô cơ, không tái chế được"},
]
# -----------------------------

# --- Cấu hình Trang Web ---
st.set_page_config(page_title="Project_2", layout="centered")


# =========================================================================
# === KHU VỰC GIỚI THIỆU TRONG SIDEBAR ===
# =========================================================================

st.sidebar.title("🌱 AI Phân Loại Rác")
st.sidebar.markdown("""
👋 **Chào bạn!** Web này giúp bạn:
- 📸 Chụp ảnh rác  
- ✍️ Nhập mô tả  
- 🤖 Nhận tư vấn phân loại
- 📜 Xem lại lịch sử

---

### ♻️ Các loại rác:
- **Tái chế**: chai nhựa, lon, giấy
- **Hữu cơ**: thức ăn thừa, vỏ trái cây
- **Vô cơ**: pin, gốm, rác khó phân hủy

---

💡 *Hãy cùng nhau bảo vệ môi trường!*
""")


# =========================================================================
# === KHU VỰC HIỂN THỊ LỊCH SỬ VÀ NÚT XÓA (SIDEBAR) ===
# =========================================================================

st.sidebar.markdown("---")
st.sidebar.title("📜 LỊCH SỬ PHÂN LOẠI")

def clear_history():
    st.session_state.history = []
    st.sidebar.success("Đã xóa lịch sử!") # Thông báo thành công khi xóa

if st.session_state.history:
    
    # NÚT XÓA LỊCH SỬ 
    st.sidebar.button("🗑️ Xóa toàn bộ lịch sử", on_click=clear_history) 

    # HIỂN THỊ LỊCH SỬ
    for i, item in enumerate(reversed(st.session_state.history), 1):
        with st.sidebar.expander(f"🔹 Lần {i} - [{item['time']}]"):
            st.markdown(f"**Nguồn ảnh:** {item['image']}")
            st.markdown(f"**Yêu cầu:** {item['input']}")
            st.markdown(f"**Phản hồi Gemini:** {item['response']}")
        st.sidebar.markdown("---")
else:
    st.sidebar.info("Chưa có lịch sử nào trong phiên này.")


# =========================================================================
# === KHU VỰC CHÍNH CỦA ỨNG DỤNG (CÓ TAB) ===
# =========================================================================

st.title("🚮 Trang Web Hỗ Trợ Phân Loại Rác & Bảo Vệ Môi Trường")

# ✅ BƯỚC 1 — TẠO TAB MENU
tab1, tab2 = st.tabs(["♻️ Phân loại rác", "📊 Thống kê & Insight"])


# ✅ BƯỚC 2 — BỌC TOÀN BỘ CODE PHÂN LOẠI VÀO tab1
with tab1:
    st.info(f"AI đang hoạt động với vai trò: **Chuyên gia Phân loại Rác**")

    if client: 
        # --- Thiết lập Cổng nhập liệu Ảnh và Văn bản ---

        # 1. Khu vực Chụp Ảnh trực tiếp (ƯU TIÊN HÀNG ĐẦU)
        camera_image = st.camera_input("📸 Bước 1: Chụp ảnh rác bạn muốn phân loại")

        # 2. Khu vực Tải lên Tệp (Dự phòng)
        uploaded_file = st.file_uploader(
            "Hoặc Tải lên hình ảnh về rác bạn muốn phân loại (JPG, PNG)", 
            type=["jpg", "jpeg", "png"]
        )
        
        user_prompt = st.text_area(
            "Bước 2: Miêu tả thêm về rác bạn muốn phân loại (Không bắt buộc):",
            height=100
        )

        # --- LOGIC ƯU TIÊN ẢNH ---
        image_to_process = None
        image_source_name = None
        if camera_image is not None:
            # Ưu tiên số 1: Ảnh chụp từ camera
            image_to_process = Image.open(camera_image)
            image_source_name = "Ảnh chụp Camera"
        elif uploaded_file is not None:
            # Ưu tiên số 2: Ảnh được tải lên
            image_to_process = Image.open(uploaded_file)
            image_source_name = f"Tệp: {uploaded_file.name}"
            
        
        # Hiển thị ảnh đã chọn/chụp (nếu có)
        if image_to_process:
            st.image(image_to_process, caption='Hình ảnh rác đang chờ phân loại.', use_column_width=True)
        
        # Nút bấm để gửi yêu cầu
        if st.button("♻️ Gửi!!", disabled=not (user_prompt or image_to_process)):
            
            # Kiểm tra dữ liệu đầu vào tối thiểu
            if not user_prompt and not image_to_process:
                st.warning("Vui lòng nhập miêu tả HOẶC chụp/tải lên hình ảnh rác để bắt đầu phân loại.")
                
            else:
                # --- Chuẩn bị Nội dung (bao gồm cả System Prompt) ---
                
                # 1. Thêm System Instruction
                contents = [SYSTEM_INSTRUCTION]

                # 2. Thêm hình ảnh đã chọn/chụp
                if image_to_process:
                    contents.append(image_to_process)
                
                # 3. Thêm Prompt của Người Dùng (hoặc thông báo rỗng nếu không nhập)
                input_text = user_prompt if user_prompt else "(Chỉ cung cấp hình ảnh)"
                contents.append(input_text)

                with st.spinner("Đang suy nghĩ và đưa ra lời khuyên để phân loại rác và bảo vệ môi trường..."):
                    try:
                        # GỌI API BẰNG HÀM FAILOVER MỚI
                        response = safe_generate_content(
                            model='gemini-2.5-flash', 
                            contents=contents
                        )
                        
                        # Hiển thị kết quả (TRƯỜNG HỢP THÀNH CÔNG)
                        st.subheader("🗑️:")
                        st.markdown(response.text)

                        # --- LƯU VÀO LỊCH SỬ ---
                        st.session_state.history.append({
                            'time': datetime.now().strftime("%H:%M:%S"),
                            'input': input_text,
                            'image': image_source_name if image_to_process else "Không có ảnh",
                            'response': response.text # Lưu phản hồi vào khóa 'response'
                        })
                        # ------------------------------------
                        
                    except APIError as e:
                        # Logic bắt lỗi đã được tinh chỉnh theo yêu cầu
                        error_str = str(e)
                        
                        if "429" in error_str:
                            # Bao gồm lỗi failover cuối cùng (cũng có 429) và lỗi hết hạn mức ngày
                            st.error("Hôm nay bạn đã dùng hết lượt miễn phí. Vui lòng quay lại vào ngày mai.")
                        elif "quota" in error_str:
                            # Bao gồm lỗi quá tải hệ thống/quota tạm thời
                            st.info("Hiện tại hệ thống đang quá tải. Vui lòng thử lại sau.")
                        else:
                            # Các lỗi khác (403, lỗi mô hình, lỗi không xác định) đều hiện lỗi API
                            st.error(f"Lỗi API: {e}")
                    except Exception as e:
                        st.error(f"Lỗi không xác định: {e}")

    else:
        # Lỗi nếu không tìm thấy bất kỳ Khóa API nào
        st.error("Không tìm thấy Khóa API hợp lệ (GEMINI_API_KEY_1, _2, _3) nào. Vui lòng kiểm tra Secrets.")


# ✅ BƯỚC 4 — TẠO TAB 2: THỐNG KÊ + BIỂU ĐỒ + INSIGHT
with tab2:
    st.header("📊 Thống kê phân loại rác")

    # Nếu dữ liệu thật < 5 thì dùng dữ liệu mẫu
    if len(st.session_state.history) < 5:
        st.info("⚠️ Dữ liệu hiện tại còn ít, đang dùng DỮ LIỆU MẪU để minh họa.")
        data_to_use = sample_data
    else:
        # SỬ DỤNG DỮ LIỆU THẬT
        data_to_use = st.session_state.history

    # Đếm số lượng từng loại rác
    recycle = 0
    organic = 0
    other = 0

    for item in data_to_use:
        # CHÚ Ý: ĐÃ SỬA TÊN KHÓA TỪ 'result' SANG 'response' để khớp với code lưu lịch sử
        text = item["response"].lower() 
        if "tái chế" in text or "tái" in text:
            recycle += 1
        elif "hữu cơ" in text or "hữu" in text:
            organic += 1
        else:
            other += 1

    total = recycle + organic + other

    if total == 0:
        st.warning("Chưa có dữ liệu nào để phân tích!")
    else:
        st.write("### ✅ Số liệu phân loại:")
        st.write(f"- ♻️ Tái chế: {recycle}")
        st.write(f"- 🌿 Hữu cơ: {organic}")
        st.write(f"- 🗑️ Vô cơ: {other}")

        st.write("### 📈 Biểu đồ phân loại")
        chart_data = {
            "Tái chế": recycle,
            "Hữu cơ": organic,
            "Vô cơ": other
        }
        # Hiển thị biểu đồ cột 
        st.bar_chart(chart_data)

        st.write("## 🧠 Nhận xét & Insight")

        if recycle > organic and recycle > other:
            st.success("✅ Phần lớn rác có thể tái chế – đây là tín hiệu rất tích cực cho môi trường.")
        elif organic > recycle and organic > other:
            st.warning("🌿 Rác hữu cơ chiếm tỉ lệ cao – bạn nên ủ rác hữu cơ để làm phân bón.")
        else:
            st.error("🗑️ Rác vô cơ đang chiếm nhiều – cần hạn chế nhựa và đồ dùng một lần.")