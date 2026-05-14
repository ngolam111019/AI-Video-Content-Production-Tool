import os
import shutil
from moviepy import AudioFileClip, CompositeAudioClip, concatenate_audioclips
from moviepy.audio.AudioClip import AudioClip

from utils.time_utils import format_timestamp, process_and_shift_srt
from utils.excel_utils import get_project_settings

def step_5_audio_processing(p_root, p_name):
    print(f"\n--- [5] Xử lý Audio & SRT ---")
    print("1. Gom nhóm 3 part (Logic hiện tại - Có SRT gộp)")
    print("2. Gộp tất cả thành 1 file duy nhất (Logic mới - Không SRT gộp)")
    choice = input("👉 Chọn chế độ (1/2): ")
    
    excel_path = os.path.join(p_root, f"{p_name}.xlsx")
    settings = get_project_settings(excel_path)
    start_padding = float(settings.get('start_padding', 2.0))
    end_padding = float(settings.get('end_padding', 3.0))

    audio_dir = os.path.join(p_root, "audio_by_parts")
    srt_dir = os.path.join(p_root, "srts")
    out_dir = os.path.join(p_root, "audios")
    os.makedirs(out_dir, exist_ok=True)
    
    # FIX: Tạo thư mục srts nếu thiếu để tránh FileNotFoundError
    if not os.path.exists(srt_dir): os.makedirs(srt_dir, exist_ok=True)

    audio_files = sorted([f for f in os.listdir(audio_dir) if f.lower().endswith(('.mp3', '.wav', '.m4a'))])
    srt_files = sorted([f for f in os.listdir(srt_dir) if f.lower().endswith('.srt')])
    
    if not audio_files:
        print("❌ Không tìm thấy file audio"); return

    merged_srt_blocks = []
    srt_counter = 1
    timestamp_lines = ["00:00 hook"]
    all_processed_temp_paths = []

    # --- XỬ LÝ PART 01 (HOOK): +2s đầu & +6s cuối ---
    print("  🎙️ Đang xử lý Part 01 (Hook): +2s đầu & +6s cuối...")
    hook_raw_p = os.path.join(audio_dir, audio_files[0])
    with AudioFileClip(hook_raw_p) as hook_raw:
        hook_total_dur = hook_raw.duration + start_padding + 6
        sil_leading = AudioClip(lambda t: [0, 0], duration=start_padding, fps=44100)
        hook_final = CompositeAudioClip([sil_leading, hook_raw.with_start(start_padding)]).with_duration(hook_total_dur)
        
        temp_hook_p = os.path.join(p_root, "temp_processed_01.mp3")
        hook_final.write_audiofile(temp_hook_p, logger=None)
        all_processed_temp_paths.append(temp_hook_p)
        
        if choice == "1":
            shutil.copy(temp_hook_p, os.path.join(out_dir, "part_01_hook.mp3"))
            if srt_files:
                blocks, srt_counter = process_and_shift_srt(os.path.join(srt_dir, srt_files[0]), start_padding, srt_counter)
                merged_srt_blocks.extend(blocks)

    current_time_acc = hook_total_dur 

    # --- XỬ LÝ CÁC PART THÂN BÀI (TỪ PART 02) ---
    print("  🎙️ Đang chuẩn bị các part thân bài...")
    for idx in range(1, len(audio_files)):
        p_id_str = f"{idx + 1:02d}"
        timestamp_lines.append(f"{format_timestamp(current_time_acc)} part {p_id_str}")
        
        with AudioFileClip(os.path.join(audio_dir, audio_files[idx])) as clip:
            p_dur = clip.duration
            sil2 = AudioClip(lambda t: [0,0], duration=start_padding)
            sil3 = AudioClip(lambda t: [0,0], duration=end_padding)
            padded = CompositeAudioClip([sil2, clip.with_start(start_padding), sil3.with_start(start_padding + p_dur)]).with_duration(start_padding + p_dur + end_padding)
            
            temp_p = os.path.join(p_root, f"temp_processed_{p_id_str}.mp3")
            padded.write_audiofile(temp_p, logger=None)
            all_processed_temp_paths.append(temp_p)
            
            # Chỉ gộp SRT nếu chọn Chế độ 1
            if choice == "1" and idx < len(srt_files):
                blocks, srt_counter = process_and_shift_srt(os.path.join(srt_dir, srt_files[idx]), current_time_acc + start_padding, srt_counter)
                merged_srt_blocks.extend(blocks)
            
            current_time_acc += (start_padding + p_dur + end_padding)

    # --- GỘP THEO CHẾ ĐỘ ---
    if choice == "1":
        print("  🎙️ Đang gom nhóm 3 part...")
        for i in range(1, len(all_processed_temp_paths), 3):
            group_paths = all_processed_temp_paths[i:i+3]
            group_clips = [AudioFileClip(p) for p in group_paths]
            p_indices = [os.path.basename(p).split('_')[2].replace('.mp3', '') for p in group_paths]
            out_name = f"part_{'_'.join(p_indices)}.mp3"
            concatenate_audioclips(group_clips).write_audiofile(os.path.join(out_dir, out_name), logger=None)
            for c in group_clips: c.close()
            
        final_srt_path = os.path.join(out_dir, f"{p_name}.srt")
        with open(final_srt_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(merged_srt_blocks))

    elif choice == "2":
        print("  🎙️ Đang gộp toàn bộ thành 1 file duy nhất...")
        all_clips = [AudioFileClip(p) for p in all_processed_temp_paths]
        out_name = f"{p_name}_full_audio.mp3"
        concatenate_audioclips(all_clips).write_audiofile(os.path.join(out_dir, out_name), logger=None)
        for c in all_clips: c.close()

    # --- KẾT THÚC ---
    timestamp_lines.append(f"{format_timestamp(current_time_acc)} outro")
    with open(os.path.join(p_root, "timestamps.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(timestamp_lines))
    
    for p in all_processed_temp_paths:
        if os.path.exists(p): os.remove(p)
    
    print(f"✅ Xong! Chế độ {choice} đã hoàn tất.")
