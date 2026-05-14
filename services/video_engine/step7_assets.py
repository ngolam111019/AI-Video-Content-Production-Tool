import os
from moviepy import VideoFileClip, ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
import moviepy.video.fx as vfx

from core.config import BASE_DIR, HD_RES, FPS

def step_7_standardize_assets():
    print(f"\n--- [7] Chuẩn hóa Video trong thư mục /videos ---")
    target_dir = os.path.join(BASE_DIR, "videos")
    
    if not os.path.exists(target_dir):
        print(f"❌ Không tìm thấy thư mục: {target_dir}"); return

    # Tạo thư mục con để chứa kết quả đã chuẩn hóa, tránh ghi đè file gốc
    std_dir = os.path.join(target_dir, "standardized")
    os.makedirs(std_dir, exist_ok=True)

    valid_exts = ('.mp4', '.mov', '.avi', '.mkv')
    files = [f for f in os.listdir(target_dir) if f.lower().endswith(valid_exts)]

    if not files:
        print("Empty: Không có video nào cần chuẩn hóa."); return

    print(f"🚀 Tìm thấy {len(files)} file. Bắt đầu chuẩn hóa về chuẩn 'The Subtext'...")

    for f_name in files:
        in_p = os.path.join(target_dir, f_name)
        out_p = os.path.join(std_dir, f_name)
        
        print(f"  🔄 Đang xử lý: {f_name}...")
        try:
            with VideoFileClip(in_p) as clip:
                # 1. Resize về HD_RES (1920x1080) - Thêm padding đen nếu khác tỷ lệ
                if clip.size != HD_RES:
                    # Giữ tỷ lệ và thêm padding để không bị méo hình
                    final_clip = clip.with_effects([vfx.Resize(height=HD_RES[1])])
                    if final_clip.w > HD_RES[0]:
                        final_clip = final_clip.with_effects([vfx.Resize(width=HD_RES[0])])
                    
                    # Tạo background đen để fit đúng 1920x1080
                    bg = ColorClip(size=HD_RES, color=(0,0,0), duration=clip.duration)
                    final_clip = CompositeVideoClip([bg, final_clip.with_position("center")])
                else:
                    final_clip = clip

                # 2. Fix FPS về chuẩn 30
                final_clip.fps = FPS

                # 3. Xuất file với đúng thông số của Bước 4
                final_clip.write_videofile(
                    out_p,
                    codec="h264_videotoolbox", # Tận dụng phần cứng Mac của bạn
                    audio_codec="aac",
                    audio_bitrate="192k",
                    audio_fps=44100,
                    bitrate="8000k",
                    logger=None
                )
            print(f"  ✅ Đã xong: {f_name} -> videos/standardized/")
        except Exception as e:
            print(f"  ❌ Lỗi file {f_name}: {e}")

    print(f"\n👉 Xong! Hãy sử dụng các file trong thư mục 'videos/standardized' để nối ở Bước 6.")
