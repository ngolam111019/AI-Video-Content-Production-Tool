import os
import time
import base64
import pandas as pd
import requests
from pathlib import Path
from core.config import (
    TTS_PROVIDER,
    VIMIX_API_KEY, VIMIX_BASE_URL, VIMIX_VOICE_ID, VIMIX_PROVIDER, VIMIX_MAX_CONCURRENT_JOBS,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID
)
from utils.time_utils import seconds_to_srt_time

def download_file(url, save_path):
    if not url: return False
    try:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
    except: pass
    return False

def save_excel_safe(excel_path, sheets_dict):
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for name, df in sheets_dict.items():
            df.to_excel(writer, sheet_name=name, index=False)

def _process_tts(project_name, project_path, excel_path):
    audio_dir = Path(project_path) / "audio_by_parts"
    srt_dir = Path(project_path) / "srts"

    audio_dir.mkdir(parents=True, exist_ok=True)
    srt_dir.mkdir(parents=True, exist_ok=True)

    if not Path(excel_path).exists():
        print(f"❌ Không tìm thấy file: {excel_path}")
        return

    excel_file = pd.ExcelFile(excel_path)
    all_sheets = {name: excel_file.parse(name) for name in excel_file.sheet_names}
    
    priority_order = ['script', 'hook']
    target_sheets = [s for s in priority_order if s in all_sheets]

    if not target_sheets:
        print(f"❌ File Excel không có sheet 'script' hoặc 'hook' nào cả!")
        return

    print(f"📂 Thứ tự xử lý: {target_sheets}")
    
    headers = {
        "Authorization": f"Bearer {VIMIX_API_KEY}",
        "Content-Type": "application/json"
    }

    for sheet_name in target_sheets:
        print(f"\n🚀 === ĐANG XỬ LÝ SHEET: [{sheet_name.upper()}] ===")
        df = all_sheets[sheet_name]

        for col in ['status_buoc_1', 'task-id']:
            if col not in df.columns:
                df[col] = ""
        df['status_buoc_1'] = df['status_buoc_1'].fillna("").astype(str)
        df['task-id'] = df['task-id'].fillna("").astype(str)

        while True:
            pending_mask = df['status_buoc_1'] == 'PENDING'
            running_count = pending_mask.sum()
            
            # Chỉ gửi những job chưa từng chạy hoặc cần thử lại (tránh gửi lại liên tục các job bị lỗi API)
            to_submit = df[df['status_buoc_1'].isin(["", "nan", "RETRY", "RETRY_DOWNLOAD"])]
            
            for index, row in to_submit.iterrows():
                if running_count >= VIMIX_MAX_CONCURRENT_JOBS:
                    break
                
                block_name = str(row.get('block', f"{sheet_name}_{index}"))
                script_text = str(row.get('script', ''))

                if not script_text.strip() or script_text.lower() == "nan":
                    df.at[index, 'status_buoc_1'] = "SKIPPED_EMPTY"
                    continue

                print(f"📤 [{sheet_name}] Gửi Job: {block_name}...")
                payload = {
                    "text": script_text,
                    "voice": VIMIX_VOICE_ID,
                    "provider": VIMIX_PROVIDER,
                    "title": f"{sheet_name}_{block_name}",
                    "withSrt": True,
                    "model": "eleven_v3"
                }

                try:
                    res = requests.post(f"{VIMIX_BASE_URL}/tts", json=payload, headers=headers, timeout=20).json()
                    if res.get("success"):
                        df.at[index, 'task-id'] = res["taskId"]
                        df.at[index, 'status_buoc_1'] = "PENDING"
                        running_count += 1
                    else:
                        err_msg = res.get("error", {}).get("message") or res.get("message") or "API Error"
                        df.at[index, 'status_buoc_1'] = f"ERROR: {err_msg}"
                        print(f"❌ [{sheet_name}] Job {block_name} Lỗi API: {err_msg}")
                except Exception as e:
                    print(f"⚠️ Mất kết nối khi gửi, sẽ thử lại sau: {e}")
                
                save_excel_safe(excel_path, all_sheets)

            for index, row in df[df['status_buoc_1'] == 'PENDING'].iterrows():
                task_id = row['task-id']
                block_name = str(row['block'])
                
                try:
                    status_res = requests.get(f"{VIMIX_BASE_URL}/tts/{task_id}", headers=headers, timeout=15).json()
                    job_status = status_res.get("status")

                    if job_status == "COMPLETED":
                        print(f"✅ [{sheet_name}] Job {block_name} DONE. Tải file...")
                        audio_url = status_res["result"].get("audioUrl")
                        srt_url = status_res["result"].get("srtUrl")

                        dl_mp3 = download_file(audio_url, audio_dir / f"{block_name}.mp3")
                        dl_srt = download_file(srt_url, srt_dir / f"{block_name}.srt") if srt_url else True

                        if dl_mp3 and dl_srt:
                            df.at[index, 'status_buoc_1'] = "COMPLETED"
                        else:
                            df.at[index, 'status_buoc_1'] = "RETRY_DOWNLOAD"
                        
                        save_excel_safe(excel_path, all_sheets)

                    elif job_status == "FAILED":
                        fail_msg = status_res.get('error', {}).get('message', 'Unknown')
                        print(f"❌ Job {block_name} FAILED: {fail_msg}")
                        df.at[index, 'status_buoc_1'] = f"FAILED: {fail_msg}"
                        save_excel_safe(excel_path, all_sheets)

                except Exception as e:
                    print(f"⏳ Đang đợi check status {block_name}...")

            active_jobs = len(df[df['status_buoc_1'].isin(['PENDING', '', 'nan', 'RETRY', 'RETRY_DOWNLOAD'])])
            if active_jobs == 0:
                print(f"🏁 Dừng xử lý sheet: {sheet_name} (Các job đã Hoàn thành hoặc bị Lỗi)")
                break
                
            time.sleep(4)

    print("\n✨ TẤT CẢ CÁC SHEET ĐÃ XỬ LÝ XONG!")

def _process_elevenlabs_tts(project_name, project_path, excel_path):
    audio_dir = Path(project_path) / "audio_by_parts"
    srt_dir = Path(project_path) / "srts"

    audio_dir.mkdir(parents=True, exist_ok=True)
    srt_dir.mkdir(parents=True, exist_ok=True)

    if not Path(excel_path).exists():
        print(f"❌ Không tìm thấy file: {excel_path}")
        return

    excel_file = pd.ExcelFile(excel_path)
    all_sheets = {name: excel_file.parse(name) for name in excel_file.sheet_names}
    
    priority_order = ['script', 'hook']
    target_sheets = [s for s in priority_order if s in all_sheets]

    if not target_sheets:
        print(f"❌ File Excel không có sheet 'script' hoặc 'hook' nào cả!")
        return

    print(f"📂 Thứ tự xử lý (ElevenLabs Provider): {target_sheets}")
    if not ELEVENLABS_API_KEY or ELEVENLABS_API_KEY.strip() == "":
        print("❌ CẢNH BÁO: Chưa cấu hình ELEVENLABS_API_KEY trong file .env!")
        return

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/with-timestamps"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }

    for sheet_name in target_sheets:
        print(f"\n🚀 === ĐANG XỬ LÝ SHEET: [{sheet_name.upper()}] (ELEVENLABS) ===")
        df = all_sheets[sheet_name]

        for col in ['status_buoc_1', 'task-id']:
            if col not in df.columns:
                df[col] = ""
        df['status_buoc_1'] = df['status_buoc_1'].fillna("").astype(str)

        to_submit = df[df['status_buoc_1'].isin(["", "nan", "RETRY", "RETRY_DOWNLOAD"])]
        if to_submit.empty:
            print(f"✨ Không có job nào cần chạy trong sheet {sheet_name}.")
            continue

        for index, row in to_submit.iterrows():
            block_name = str(row.get('block', f"{sheet_name}_{index}"))
            script_text = str(row.get('script', ''))

            if not script_text.strip() or script_text.lower() == "nan":
                df.at[index, 'status_buoc_1'] = "SKIPPED_EMPTY"
                save_excel_safe(excel_path, all_sheets)
                continue

            print(f"📤 [{sheet_name}] Gọi API ElevenLabs: {block_name}...")
            payload = {
                "text": script_text,
                "model_id": "eleven_v3",
                "output_format": "mp3_44100_128"
            }

            try:
                res = requests.post(url, json=payload, headers=headers, timeout=60)
                if res.status_code == 200:
                    data = res.json()
                    audio_b64 = data.get("audio_base64")
                    if audio_b64:
                        mp3_path = audio_dir / f"{block_name}.mp3"
                        with open(mp3_path, "wb") as f_mp3:
                            f_mp3.write(base64.b64decode(audio_b64))

                        alignment = data.get("alignment", {})
                        chars = alignment.get("characters", [])
                        starts = alignment.get("character_start_times_seconds", [])
                        ends = alignment.get("character_end_times_seconds", [])

                        words = []
                        curr_word = ""
                        w_start = 0.0
                        w_end = 0.0

                        for c, s, e in zip(chars, starts, ends):
                            if c.strip():
                                if not curr_word:
                                    w_start = s
                                curr_word += c
                                w_end = e
                            else:
                                if curr_word:
                                    words.append((curr_word, w_start, w_end))
                                    curr_word = ""
                        if curr_word:
                            words.append((curr_word, w_start, w_end))

                        srt_blocks = []
                        block_idx = 1
                        i = 0
                        while i < len(words):
                            chunk = words[i:i+10]
                            chunk_start = chunk[0][1]
                            chunk_end = chunk[-1][2]
                            chunk_text = " ".join([w[0] for w in chunk])
                            srt_blocks.append(f"{block_idx}\n{seconds_to_srt_time(chunk_start)} --> {seconds_to_srt_time(chunk_end)}\n{chunk_text}")
                            block_idx += 1
                            i += 10

                        srt_path = srt_dir / f"{block_name}.srt"
                        with open(srt_path, "w", encoding="utf-8") as f_srt:
                            f_srt.write("\n\n".join(srt_blocks))

                        df.at[index, 'status_buoc_1'] = "COMPLETED"
                        print(f"✅ [{sheet_name}] Job {block_name} DONE (ElevenLabs).")
                    else:
                        df.at[index, 'status_buoc_1'] = "ERROR: No audio returned"
                        print(f"❌ [{sheet_name}] Job {block_name} Lỗi: Không nhận được dữ liệu âm thanh")
                else:
                    try:
                        err_msg = res.json().get("detail", {}).get("message") or res.json().get("message") or res.text
                    except:
                        err_msg = res.text
                    df.at[index, 'status_buoc_1'] = f"ERROR: {err_msg[:100]}"
                    print(f"❌ [{sheet_name}] Job {block_name} Lỗi ElevenLabs API ({res.status_code}): {err_msg}")
            except Exception as e:
                print(f"⚠️ Lỗi kết nối ElevenLabs: {e}")
                df.at[index, 'status_buoc_1'] = f"ERROR: Connection Failed"
            
            save_excel_safe(excel_path, all_sheets)
            time.sleep(1)

    print("\n✨ TẤT CẢ CÁC SHEET ĐÃ XỬ LÝ XONG (ELEVENLABS)!")

def step_9_generate_audio(project_path, p_name, excel_path):
    print(f"\n--- BƯỚC 9: TẠO AUDIO & SRT TỪ SCRIPT ({TTS_PROVIDER}) ---")
    if TTS_PROVIDER == "ELEVENLABS":
        _process_elevenlabs_tts(p_name, project_path, excel_path)
    else:
        _process_tts(p_name, project_path, excel_path)
