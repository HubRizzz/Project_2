import os
import streamlit as st
from google import genai
from google.genai.errors import APIError
from PIL import Image
import io
from datetime import datetime

# ⚠️ CẢNH BÁO: Đặt Khóa API trực tiếp vào code không được khuyến nghị!
MY_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Khởi tạo Client Gemini toàn cục
@st.cache_resource
def get_gemini_client():
    try:
        # Khởi tạo client với Khóa API đã đặt
        client = genai.Client(api_key=MY_GEMINI_API_KEY)
        return client
    except Exception as e:
        # st.error sẽ chỉ hiển thị khi client được gọi lần đầu
        # Nếu khóa API rỗng, lỗi sẽ là 'API key must be provided'
        st.error(f"Lỗi khởi tạo Gemini Client: Vui lòng kiểm tra lại Khóa API.")
        return None

client = get_gemini_client()

# --- PROMPT CỐ ĐỊNH CỦA HỆ THỐNG (SYSTEM INSTRUCTION) ---
SYSTEM_INSTRUCTION = (
    "Bạn là một chuyên gia bảo vệ môi trường thân thiện. "
    "Mọi câu trả lời của bạn phải là về phân loại rác thải, giải thích tại sao rác đó nên được phân loại vào loại đó (Tái chế, Hữu cơ, Vô cơ/Khác) và đưa ra lời khuyên để giảm thiểu rác. "
    "Nếu người dùng không cung cấp đủ thông tin (văn bản hoặc hình ảnh), hãy lịch sự yêu cầu họ cung cấp thêm thông tin để bạn có thể phân loại."
    
    "Trả lời ngắn gọn trong 1 câu"
)
# -----------------------------------------------------------------

# --- KHỞI TẠO BỘ NHỚ LỊCH SỬ ---
if 'history' not in st.session_state:
    st.session_state.history = []
# -----------------------------

# --- Cấu hình Trang Web ---
st.set_page_config(page_title="Project_2", layout="centered")


# =========================================================================
# === KHU VỰC GIỚI THIỆU TRONG SIDEBAR (BƯỚC 1) ===
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

💡 *Hãy cùng bảo vệ môi trường!*
""")


# =========================================================================
# === KHU VỰC HIỂN THỊ LỊCH SỬ VÀ NÚT XÓA (BƯỚC 2 & 3) ===
# =========================================================================

st.sidebar.markdown("---")
st.sidebar.title("📜 LỊCH SỬ PHÂN LOẠI")

def clear_history():
    st.session_state.history = []
    st.sidebar.success("Đã xóa lịch sử!") # Thông báo thành công khi xóa

if st.session_state.history:
    
    # NÚT XÓA LỊCH SỬ (BƯỚC 3)
    # on_click được dùng để chạy hàm clear_history mà không cần khối if/else bên ngoài
    st.sidebar.button("🗑️ Xóa toàn bộ lịch sử", on_click=clear_history) 

    # HIỂN THỊ LỊCH SỬ (BƯỚC 2 - Phiên bản tối ưu hơn)
    for i, item in enumerate(reversed(st.session_state.history), 1):
        st.sidebar.markdown(f"### 🔹 Lần {i}")
        st.sidebar.write("🕒", item["time"])
        # Dùng tên khóa đã lưu là 'input' và 'response'
        st.sidebar.write("👤 Mô tả:", item["input"])
        st.sidebar.write("🤖 Kết quả:", item["response"])
        st.sidebar.markdown("---")
else:
    st.sidebar.info("Chưa có lịch sử nào trong phiên này.")


# =========================================================================
# === KHU VỰC CHÍNH CỦA ỨNG DỤNG ===
# =========================================================================

st.title("🚮 Trang Web Hỗ Trợ Phân Loại Rác & Bảo Vệ Môi Trường")
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
                    # Gọi API Gemini
                    response = client.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=contents
                    )
                    
                    # Hiển thị kết quả
                    st.subheader("🗑️:")
                    st.markdown(response.text)

                    # --- LƯU VÀO LỊCH SỬ ---
                    st.session_state.history.append({
                        'time': datetime.now().strftime("%H:%M:%S"),
                        'input': input_text,
                        'image': image_source_name if image_to_process else "Không có ảnh",
                        'response': response.text
                    })
                    # ------------------------------------
                    
                except APIError as e:
                    # Logic bắt lỗi đã thêm trước đó:
                    if "429" in str(e):
                        st.error("Hôm nay bạn đã dùng hết lượt miễn phí. Vui lòng quay lại vào ngày mai.")
                    elif "quota" in str(e):
                        st.info("Hiện tại hệ thống đang quá tải. Vui lòng thử lại sau.")
                    else:
                        st.error(f"Lỗi API: {e}")
                except Exception as e:
                    st.error(f"Lỗi không xác định: {e}")
else:
    st.error("Không thể kết nối với Gemini API. Vui lòng kiểm tra lại Khóa API đã được điền.")