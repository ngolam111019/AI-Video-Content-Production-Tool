import os
import subprocess
from moviepy import VideoFileClip, ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
import moviepy.video.fx as vfx
from utils.time_utils import format_timestamp, process_and_shift_srt
from core.config import HD_RES, FPS
from utils.excel_utils import get_project_settings

def step_6_final_merge(p_root, p_name, excel_path):
    print(f"\n--- [6] Nối Video, Xử lý SRT & Tạo Timestamps ---")
    
    settings = get_project_settings(excel_path)
    start_padding = float(settings.get('start_padding', 2.0))
    
    prod_dir = os.path.join(p_root, "production_parts")
    hook_dir = os.path.join(p_root, "hook")
    srt_dir = os.path.join(p_root, "srts")
    list_path = os.path.join(p_root, "concat_list.txt")
    timestamp_path = os.path.join(p_root, "timestamps.txt")
    
    final_srt_blocks = []
    timestamp_lines = []
    current_idx_srt = 1
    current_global_time = 0.0 

    # --- PHẦN 1: XỬ LÝ HOOK (BLOCK 1) ---
    hook_std_p = None
    if os.path.exists(hook_dir):
        hook_files = [f for f in os.listdir(hook_dir) if f.lower().endswith(".mp4")]
        
        if hook_files:
            # SỬA LỖI: Chọn file thủ công, nếu chưa có std_hook thì tự động chuẩn hóa
            std_candidates = [hf for hf in hook_files if hf.startswith("std_")]
            if std_candidates:
                chosen_hook_name = std_candidates[0]
                hook_std_p = os.path.join(hook_dir, chosen_hook_name)
            else:
                original_hook_name = hook_files[0]
                original_hook_p = os.path.join(hook_dir, original_hook_name)
                chosen_hook_name = f"std_{original_hook_name}"
                hook_std_p = os.path.join(hook_dir, chosen_hook_name)
                
                print(f"  🔄 Đang chuẩn hóa Hook: {original_hook_name}...")
                try:
                    with VideoFileClip(original_hook_p) as clip:
                        if clip.size != HD_RES:
                            final_clip = clip.with_effects([vfx.Resize(height=HD_RES[1])])
                            if final_clip.w > HD_RES[0]:
                                final_clip = final_clip.with_effects([vfx.Resize(width=HD_RES[0])])
                            
                            bg = ColorClip(size=HD_RES, color=(0,0,0), duration=clip.duration)
                            final_clip = CompositeVideoClip([bg, final_clip.with_position("center")])
                        else:
                            final_clip = clip

                        final_clip.fps = FPS

                        final_clip.write_videofile(
                            hook_std_p,
                            codec="h264_videotoolbox",
                            audio_codec="aac",
                            audio_bitrate="192k",
                            audio_fps=44100,
                            bitrate="8000k",
                            logger=None
                        )
                    print(f"  ✅ Chuẩn hóa Hook xong: {chosen_hook_name}")
                except Exception as e:
                    print(f"  ❌ Lỗi chuẩn hóa Hook: {e}")
                    hook_std_p = None

            if hook_std_p and os.path.exists(hook_std_p):
                with VideoFileClip(hook_std_p) as v_hook:
                    # Format mới: 00:00 block 1 (hook)
                    timestamp_lines.append(f"{format_timestamp(current_global_time)} block 1 (hook)")
                    
                    # SRT Hook (1.srt) bắt đầu từ 0.0s vì Intro nằm sau lời thoại
                    hook_srt_p = os.path.join(srt_dir, "1.srt")
                    if os.path.exists(hook_srt_p):
                        print(f"  📝 Khớp SRT Hook: 0.0s offset")
                        blocks, current_idx_srt = process_and_shift_srt(hook_srt_p, 0.0, current_idx_srt)
                        final_srt_blocks.extend(blocks)
                    
                    current_global_time += v_hook.duration

    # --- PHẦN 2: XỬ LÝ CÁC PART THÂN BÀI (BLOCK 2, 3...) ---
    parts = []
    if os.path.exists(prod_dir):
        # Sort numerically: Extract number from string, if possible.
        def sort_key(f):
            num_str = ''.join(filter(str.isdigit, os.path.splitext(f)[0]))
            return int(num_str) if num_str else 0
        
        parts_raw = [f for f in os.listdir(prod_dir) if f.endswith(".mp4") and f[0].isdigit()]
        parts = sorted(parts_raw, key=sort_key)
        
        for i, p_file in enumerate(parts):
            block_id = os.path.splitext(p_file)[0]
            part_video_p = os.path.join(prod_dir, p_file)
            part_srt_p = os.path.join(srt_dir, f"{block_id}.srt")

            # Ghi nhận timestamp: Hook là block 1, nên part đầu tiên là block 2
            timestamp_lines.append(f"{format_timestamp(current_global_time)} block {i+2}")

            with VideoFileClip(part_video_p) as v_part:
                if os.path.exists(part_srt_p):
                    # Logic: Voice bắt đầu sau khoảng thời gian start_padding im lặng
                    part_offset = current_global_time + start_padding
                    print(f"  📝 Khớp SRT Part {block_id}: offset {part_offset:.2f}s")
                    
                    blocks, current_idx_srt = process_and_shift_srt(part_srt_p, part_offset, current_idx_srt)
                    final_srt_blocks.extend(blocks)
                
                current_global_time += v_part.duration

    # --- PHẦN 3: XUẤT FILE TỔNG HỢP ---
    try:
        # 1. Xuất Timestamps
        with open(timestamp_path, "w", encoding="utf-8") as f_ts:
            f_ts.write("\n".join(timestamp_lines))
        print(f"✅ Đã tạo file timestamp (Format mới): {os.path.basename(timestamp_path)}")

        # 2. Xuất SRT tổng
        srt_output_name = f"{p_name}_FINAL_FULL.srt"
        if final_srt_blocks:
            with open(os.path.join(p_root, srt_output_name), "w", encoding="utf-8") as f_srt:
                f_srt.write("\n\n".join(final_srt_blocks))
            print(f"✅ Đã tạo file phụ đề tổng: {srt_output_name}")

        # 3. Nối Video bằng FFmpeg
        with open(list_path, "w", encoding="utf-8") as f_list:
            if hook_std_p:
                f_list.write(f"file '{os.path.abspath(hook_std_p)}'\n")
            for p in parts:
                f_list.write(f"file '{os.path.abspath(os.path.join(prod_dir, p))}'\n")

        output_name = f"{p_name}_FINAL_FULL.mp4"
        print(f"  🔗 Đang nối Video bằng FFmpeg...")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", os.path.join(p_root, output_name)], capture_output=True)

        if os.path.exists(list_path): os.remove(list_path)
        print(f"🚀 HOÀN THÀNH VIDEO CHO KÊNH 'THE SUBTEXT'!")

    except Exception as e:
        print(f"❌ Lỗi gộp cuối cùng: {e}")
