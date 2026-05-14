import os
import gc
import cv2
from moviepy import ImageClip, VideoFileClip
import moviepy.video.fx as vfx
from concurrent.futures import ProcessPoolExecutor
from core.config import HD_RES, FPS
from utils.excel_utils import get_clean_df, save_to_excel

def render_single_scene(idx, row, p_root, out_dir):
    """Hàm xử lý riêng lẻ cho 1 Scene để phục vụ chạy song song"""
    file_name = str(row.get('raw_videos', '')).strip()
    target_dur = float(row.get('read_time', 0))
    
    if not file_name or file_name == 'nan' or target_dur <= 0:
        return idx, False

    in_p = os.path.join(p_root, "raw_videos", file_name)
    out_name = f"{os.path.splitext(file_name)[0]}.mp4"
    out_p = os.path.join(out_dir, out_name)

    if not os.path.exists(in_p):
        return idx, False

    try:
        # Logic Zoom: 8s = 30% (tức 1s = 0.0375)
        total_zoom_change = target_dur * 0.0375
        ext = os.path.splitext(file_name)[1].lower()

        if ext in ['.jpg', '.jpeg', '.png', '.webp']:
            img_rgb = cv2.cvtColor(cv2.imread(in_p), cv2.COLOR_BGR2RGB)
            h_orig, w_orig = img_rgb.shape[:2]
            base_scale = max(HD_RES[0] / w_orig, HD_RES[1] / h_orig)

            def make_frame_opencv(get_frame, t):
                # Sử dụng hàm smooth_quartic nội bộ bên trong
                p = t / target_dur
                progress = 8 * p**4 if p < 0.5 else 1 - 8 * (p - 1)**4
                
                if idx % 2 == 0: zoom = 1.0 + (total_zoom_change * progress)
                else: zoom = (1.0 + total_zoom_change) - (total_zoom_change * progress)
                
                M = cv2.getRotationMatrix2D((w_orig/2, h_orig/2), 0, base_scale * zoom)
                M[0, 2] += (HD_RES[0]/2) - (w_orig/2)
                M[1, 2] += (HD_RES[1]/2) - (h_orig/2)
                return cv2.warpAffine(img_rgb, M, HD_RES, flags=cv2.INTER_CUBIC)

            final = ImageClip(img_rgb).with_duration(target_dur).transform(make_frame_opencv)
        else:
            with VideoFileClip(in_p) as v:
                final = v.with_effects([vfx.MultiplySpeed(v.duration / target_dur)])
                # So sánh theo tuple để đồng nhất kiểu dữ liệu
                if tuple(final.size) != HD_RES:
                    final = final.with_effects([vfx.Resize(new_size=HD_RES)])

        final.fps = FPS
        # Xuất file với codec Mac và bitrate chuẩn 8000k
        final.write_videofile(
            out_p, 
            codec="h264_videotoolbox", 
            audio=False, 
            bitrate="8000k", 
            logger=None
        )
        return idx, True
    except Exception as e:
        print(f"❌ Lỗi Scene {idx+1} ({file_name}): {e}")
        return idx, False


def step_3_render_pacing(p_root, excel_path):
    print("\n--- [3] Render Scenes (Song song + Tối ưu tốc độ) ---")
    df = get_clean_df(excel_path, "scene")
    if df is None: return

    out_dir = os.path.join(p_root, "mastered_scenes"); os.makedirs(out_dir, exist_ok=True)
    if 'status_buoc_4' not in df.columns: df['status_buoc_4'] = ''

    # Lọc danh sách cần xử lý
    tasks = []
    for idx, row in df.iterrows():
        if str(row.get('status_buoc_4', '')).lower() != 'đã hoàn thành' and str(row.get('raw_videos', '')).strip() not in ['', 'nan']:
            tasks.append((idx, row))

    if not tasks:
        print("✅ Tất cả các scene đã hoàn thành."); return

    print(f"🚀 Đang render {len(tasks)} scene song song...")
    
    # Sử dụng ProcessPoolExecutor để chạy song song (giới hạn max_workers để tránh tràn RAM)
    # Chip M1/M2/M3 nên để khoảng 2-4 workers cho video
    with ProcessPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(render_single_scene, idx, row, p_root, out_dir) for idx, row in tasks]
        
        for future in futures:
            idx, success = future.result()
            if success:
                df.at[idx, 'status_buoc_4'] = 'Đã hoàn thành'
                # Lưu checkpoint mỗi khi xong 1 scene để an toàn
                save_to_excel(df, excel_path, "scene")
                print(f"  🎬 Scene {idx+1:03d} OK.")

    gc.collect()
    print("✅ Bước 3 hoàn tất. Dữ liệu đã sạch, sẵn sàng cho Bước 4.")
