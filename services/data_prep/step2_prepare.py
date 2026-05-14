import os
import re
from utils.excel_utils import get_clean_df, save_to_excel, get_project_settings
from utils.media_utils import get_audio_duration_ffprobe
from utils.time_utils import parse_srt_to_word_timeline

def step_2_prepare_data(p_root, excel_path):
    print("\n--- [2] Thống kê & Đồng bộ dựa trên Key 'Block' ---")
    df_script = get_clean_df(excel_path, "script")
    df_scene = get_clean_df(excel_path, "scene")
    
    settings = get_project_settings(excel_path)
    start_padding = float(settings.get('start_padding', 2.0))
    end_padding = float(settings.get('end_padding', 3.0))
    
    if df_script is None or df_scene is None: return
    
    audio_dir = os.path.join(p_root, "audio_by_parts")
    srt_dir = os.path.join(p_root, "srts")
    os.makedirs(srt_dir, exist_ok=True)

    # Lấy danh sách tất cả file audio và srt thực tế trong thư mục để tra cứu nhanh
    actual_audios = os.listdir(audio_dir)
    actual_srts = os.listdir(srt_dir)

    # [A] Xử lý sheet SCRIPT (Làm chuẩn)
    print("  📊 Đang cập nhật thông tin âm thanh vào sheet Script...")
    # Đảm bảo cột có kiểu dữ liệu phù hợp để tránh cảnh báo pandas
    for col in ['thời gian audio']:
        if col not in df_script.columns:
            df_script[col] = 0.0
        else:
            df_script[col] = df_script[col].astype(float)

    for idx, row in df_script.iterrows():
        # Lấy nguyên giá trị cột block (ví dụ: 1.0 -> "1", "intro" -> "intro")
        block_val = str(row.get('block', '')).strip()
        block_id = str(int(float(block_val))) if block_val.replace('.','',1).isdigit() else block_val
        
        # Tìm file audio tương ứng (hỗ trợ nhiều định dạng)
        audio_file = next((f for f in actual_audios if f.startswith(f"{block_id}.")), None)
        if audio_file:
            dur = get_audio_duration_ffprobe(os.path.join(audio_dir, audio_file))
            df_script.at[idx, 'thời gian audio'] = round(dur, 3)
        
        txt = str(row.get('script', ''))
        df_script.at[idx, 'số từ'] = len(re.findall(r'\w+', txt))

    save_to_excel(df_script, excel_path, "script")

    # [B] Xử lý sheet SCENE (Dựa trên Key Block từ Script)
    print("  🎬 Đang đồng bộ Timeline cho sheet Scene...")
    
    # Đảm bảo các cột timeline là float để tránh cảnh báo pandas dtype incompatible
    for col in ['start_time', 'end_time', 'read_time']:
        if col not in df_scene.columns:
            df_scene[col] = 0.0
        else:
            df_scene[col] = df_scene[col].astype(float)
            
    # Tìm tất cả các điểm bắt đầu của block trong sheet scene
    # Lưu ý: Ta giả định block chỉ ghi ở dòng đầu tiên của mỗi đoạn trong sheet scene
    all_scene_starts = df_scene[df_scene['block'].notna()].index.tolist()
    
    for i, s_idx in enumerate(all_scene_starts):
        # Lấy giá trị nguyên bản của cột block
        raw_block = str(df_scene.at[s_idx, 'block']).strip()
        block_id = str(int(float(raw_block))) if raw_block.replace('.','',1).isdigit() else raw_block
        
        # Xác định dòng kết thúc của block này trong sheet scene
        e_idx = all_scene_starts[i+1] - 1 if i+1 < len(all_scene_starts) else len(df_scene) - 1
        
        # Tìm file SRT tương ứng dựa trên block_id
        srt_file = f"{block_id}.srt"
        srt_path = os.path.join(srt_dir, srt_file)
        
        timeline = parse_srt_to_word_timeline(srt_path) if srt_file in actual_srts else []
        cursor = 0

        for r_idx in range(s_idx, e_idx + 1):
            s_text = str(df_scene.at[r_idx, 'script'])
            s_words = len(re.findall(r'\w+', s_text))
            
            if timeline and cursor < len(timeline):
                start_t = timeline[cursor]['start']
                end_pos = min(cursor + s_words - 1, len(timeline) - 1)
                end_t = timeline[end_pos]['end']
                
                base_dur = round(max(0.1, end_t - start_t), 3)
                
                # Logic Padding dựa trên vị trí block
                padding = 0.0
                if r_idx == s_idx: 
                    padding += start_padding  # Đầu mỗi block luôn nghỉ start_padding
                
                # Nếu là block cuối cùng trong danh sách script VÀ là dòng cuối cùng của block đó
                is_last_block = (i == len(all_scene_starts) - 1)
                if is_last_block and r_idx == e_idx:
                    padding += end_padding  # Outro cuối video
                
                df_scene.at[r_idx, 'start_time'] = round(start_t, 3)
                df_scene.at[r_idx, 'end_time'] = round(end_t, 3)
                df_scene.at[r_idx, 'read_time'] = base_dur + padding
                cursor += s_words
            else:
                df_scene.at[r_idx, 'read_time'] = 0.0

    # Tự động gán video mẫu nếu chưa có
    raw_v_dir = os.path.join(p_root, "raw_videos")
    if os.path.exists(raw_v_dir):
        valid_exts = ('.mp4', '.mov', '.jpg', '.jpeg', '.png', '.webp')
        raw_files = sorted([f for f in os.listdir(raw_v_dir) if f.lower().endswith(valid_exts)])
        if raw_files:
            df_scene['raw_videos'] = [raw_files[idx % len(raw_files)] for idx in range(len(df_scene))]

    save_to_excel(df_scene, excel_path, "scene")
    print(f"✅ Đã đồng bộ thành công {len(all_scene_starts)} block dữ liệu.")
