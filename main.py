import os
import sys

def _ensure_venv():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(base_dir, '.venv')
    venv_python = os.path.join(venv_dir, 'bin', 'python3')
    
    # Kiểm tra xem cấu hình của tiến trình python có nằm trong .venv không
    if os.path.exists(venv_python) and sys.prefix != venv_dir:
        # Nếu không, tự động đổi quyền thực thi giao cho python trong .venv
        os.execl(venv_python, venv_python, *sys.argv)

_ensure_venv()

from core.config import BASE_VIDEOS_DIR
from services.data_prep.step2_prepare import step_2_prepare_data
from services.video_engine.step3_render import step_3_render_pacing
from services.video_engine.step4_master import step_4_master_parts_combined
from services.audio_engine.step5_audio import step_5_audio_processing
from services.video_engine.step6_merge import step_6_final_merge
from services.video_engine.step7_assets import step_7_standardize_assets
from services.media_gen.step8_generate_images import step_8_generate_images
from services.media_gen.step9_generate_audio import step_9_generate_audio

def run_main():
    if not os.path.exists(BASE_VIDEOS_DIR):
        print(f"❌ Không tìm thấy thư mục: {BASE_VIDEOS_DIR}")
        return

    projects = sorted([d for d in os.listdir(BASE_VIDEOS_DIR) if os.path.isdir(os.path.join(BASE_VIDEOS_DIR, d))])
    p_name = input(f"📁 Dự án: {projects}\nChọn: ")
    p_root = os.path.join(BASE_VIDEOS_DIR, p_name)
    excel_path = os.path.join(p_root, f"{p_name}.xlsx")
    
    # Bước 7 xử lý chung cho toàn bộ asset (video raw), nhưng vẫn hỏi dự án đầu tiên theo flow cũ.
    # Trong trường hợp chưa có project nào, hoặc c=7 không cần file excel, để tránh thoát nhầm:
    if c := input("\n[1] Tạo Audio & SRT từ Script \n[2] Tạo ảnh từ Prompt \n[3] Data \n[4] Render \n[5] Master Part \n[6] Final merge \n[7] Chuẩn hóa dữ liệu asset \n[8] Audio & Timestamp \nChọn: "):
        if c != "7" and not os.path.exists(excel_path):
            print(f"❌ Không tìm thấy file Excel: {excel_path}")
            return
            
        if c == "1": step_9_generate_audio(p_root, p_name, excel_path)
        elif c == "2": step_8_generate_images(p_root, excel_path)
        elif c == "3": step_2_prepare_data(p_root, excel_path)
        elif c == "4": step_3_render_pacing(p_root, excel_path)
        elif c == "5": step_4_master_parts_combined(p_root, excel_path)
        elif c == "6": step_6_final_merge(p_root, p_name, excel_path)
        elif c == "7": step_7_standardize_assets()
        elif c == "8": step_5_audio_processing(p_root, p_name)
        else: print("Lựa chọn không hợp lệ")

if __name__ == "__main__":
    try:
        run_main()
    except KeyboardInterrupt:
        print("\nĐã hủy quá trình.")
