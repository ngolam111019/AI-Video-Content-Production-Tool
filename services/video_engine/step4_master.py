import os
import gc
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips, ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.audio.AudioClip import AudioClip
from moviepy import TextClip, VideoClip
import moviepy.video.fx as vfx
import moviepy.audio.fx as afx
import re
import numpy as np
import math
from PIL import Image, ImageFilter, ImageFont, ImageDraw

def parse_srt(srt_file, max_words=12):
    if not os.path.exists(srt_file): return []
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    def srt_time_to_seconds(time_str):
        h, m, s_ms = time_str.split(':')
        s, ms = s_ms.split(',')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    blocks = []
    raw_blocks = re.split(r'\n\s*\n', content.strip())
    for rb in raw_blocks:
        lines = rb.strip().split('\n')
        if len(lines) >= 3:
            time_line = lines[1]
            if '-->' in time_line:
                t_str = time_line.split('-->')
                t_start = srt_time_to_seconds(t_str[0].strip())
                t_end = srt_time_to_seconds(t_str[1].strip())
                text = " ".join([l.strip() for l in lines[2:]])
                if text:
                    words = text.split()
                    if len(words) <= max_words:
                        blocks.append((t_start, t_end, text))
                    else:
                        total_words = len(words)
                        total_dur = t_end - t_start
                        curr_start = t_start
                        for i in range(0, total_words, max_words):
                            chunk_words = words[i:i+max_words]
                            chunk_text = " ".join(chunk_words)
                            chunk_dur = total_dur * (len(chunk_words) / total_words)
                            chunk_end = curr_start + chunk_dur
                            blocks.append((curr_start, chunk_end, chunk_text))
                            curr_start = chunk_end
    return blocks

from core.config import BASE_DIR, HD_RES, FPS
from utils.excel_utils import get_clean_df, save_to_excel, get_project_settings

def step_4_master_parts_combined(p_root, excel_path):
    print(f"\n--- [4] Gộp & Master Part (Theo Key Block + Tối ưu 1080p) ---")
    df_scene = get_clean_df(excel_path, "scene")
    if df_scene is None: return
    if 'raw_videos' not in df_scene.columns:
        print("❌ LỖI: Sheet 'scene' không có cột 'raw_videos'. Bạn cần chạy Bước [3] (Data) hoặc kiểm tra lại file Excel.")
        return
    
    settings = get_project_settings(excel_path)
    
    def check_bool(val, default):
        s = str(val).strip().lower()
        if s in ['true', '1', 'yes', 'có']: return True
        if s in ['false', '0', 'no', 'không']: return False
        return default

    enable_cta = check_bool(settings.get('enable_cta', 'true'), True)
    enable_caption = check_bool(settings.get('enable_caption', 'true'), True)

    caption_font_name = settings.get('caption_font', 'Montserrat-Bold.ttf')
    caption_size = int(settings.get('caption_size', 40))
    caption_color = settings.get('caption_color', 'white')
    caption_color_hl = settings.get('caption_color_hl', '#FFF200')
    caption_space_ratio = float(settings.get('caption_word_space', 0.8))

    bgm_audio = settings.get('bgm_audio', '01.mp3')
    cta_clip = settings.get('cta_clip', 'cta-the-subtext.mp4')
    start_padding = float(settings.get('start_padding', 2.0))
    end_padding = float(settings.get('end_padding', 3.0))
    
    # Cấu hình tài nguyên dùng chung
    bgm_path = os.path.join(BASE_DIR, "audios", bgm_audio)
    
    # Chuẩn bị CTA clip
    cta_clip_master = None
    if enable_cta:
        std_cta = os.path.join(BASE_DIR, "videos", "standardized", cta_clip)
        raw_cta = os.path.join(BASE_DIR, "videos", cta_clip)
        cta_path = std_cta if os.path.exists(std_cta) else raw_cta
        if os.path.exists(cta_path):
            cta_clip_master = VideoFileClip(cta_path)
            if tuple(cta_clip_master.size) != HD_RES:
                cta_clip_master = cta_clip_master.with_effects([vfx.Resize(new_size=HD_RES)])
            cta_clip_master.fps = FPS

    should_delete = input("🗑️ Xóa Scene lẻ sau khi gộp thành công? (y/n): ").lower() == 'y'
    col_status = 'status_buoc_5' 
    if col_status not in df_scene.columns: df_scene[col_status] = ''
    
    audio_dir = os.path.join(p_root, "audio_by_parts")
    actual_audios = os.listdir(audio_dir)
    srt_dir = os.path.join(p_root, "srts")
    actual_srts = os.listdir(srt_dir) if os.path.exists(srt_dir) else []
    
    prod_dir = os.path.join(p_root, "production_parts")
    os.makedirs(prod_dir, exist_ok=True)

    # Tìm các điểm bắt đầu của từng Block
    start_indices = df_scene[df_scene['block'].notna()].index.tolist()

    for i, s_idx in enumerate(start_indices):
        # 1. Chuẩn hóa Block ID (giữ nguyên gốc)
        raw_block = str(df_scene.at[s_idx, 'block']).strip()
        block_id = str(int(float(raw_block))) if raw_block.replace('.','',1).isdigit() else raw_block
        
        if str(df_scene.at[s_idx, col_status]).lower() == 'đã hoàn thành':
            print(f"  ⏭️ Part {block_id} đã hoàn thành, bỏ qua.")
            continue

        # 2. Truy xuất file Audio chuẩn xác dựa trên block_id
        audio_file = next((f for f in actual_audios if f.startswith(f"{block_id}.")), None)
        if not audio_file:
            print(f"  ⚠️ CẢNH BÁO: Không tìm thấy file audio cho Block {block_id}. Bỏ qua Part này.")
            continue
        
        audio_p = os.path.join(audio_dir, audio_file)
        
        srt_file = next((f for f in actual_srts if f.startswith(f"{block_id}.")), None)
        srt_blocks = []
        if srt_file:
            srt_blocks = parse_srt(os.path.join(srt_dir, srt_file), max_words=12)
            
        out_p = os.path.join(prod_dir, f"{block_id}.mp4") 
        e_idx = start_indices[i+1]-1 if i+1 < len(start_indices) else len(df_scene)-1
        
        print(f"  🎙️ Đang xử lý Part {block_id} ({i+1}/{len(start_indices)}) (Dòng {s_idx+1} -> {e_idx+1})...")
        clips = []
        is_data_clean = True
        
        # 3. Thu thập các Scene đã render từ Bước 3
        for idx in range(s_idx, e_idx + 1):
            raw_fn = str(df_scene.at[idx, 'raw_videos']).strip()
            if not raw_fn or raw_fn == 'nan': continue
            
            scene_fn = f"{os.path.splitext(raw_fn)[0]}.mp4"
            scene_p = os.path.join(p_root, "mastered_scenes", scene_fn)
            
            if os.path.exists(scene_p):
                c = VideoFileClip(scene_p, audio=False)
                if tuple(c.size) != HD_RES:
                    print(f"  ❌ LỖI: Scene '{scene_fn}' sai kích thước {c.size}. Cần chạy lại Bước 3!")
                    is_data_clean = False
                    c.close()
                    break
                clips.append(c)
            else:
                print(f"  ⚠️ Thiếu file render: {scene_fn}. Vui lòng kiểm tra lại Bước 3.")
                is_data_clean = False
                break
        
        if not is_data_clean or not clips:
            print(f"  ⏭️ Hủy bỏ gộp Part {block_id} do thiếu dữ liệu.")
            for c in clips: c.close()
            continue

        # 4. Thực hiện gộp và lồng Audio
        try:
            combined_scenes = concatenate_videoclips(clips, method="compose")
            with AudioFileClip(audio_p) as voice:
                is_last_part = (i == len(start_indices) - 1)
                content_padding = start_padding + (end_padding if is_last_part else 0.0)
                content_dur = voice.duration + content_padding
                
                cta_dur = cta_clip_master.duration if cta_clip_master else 0
                total_video_dur = content_dur + cta_dur

                # Mix nhạc nền và giọng đọc
                final_audio_layers = []
                if os.path.exists(bgm_path):
                    bgm = AudioFileClip(bgm_path)
                    if bgm.duration < total_video_dur:
                        bgm = bgm.with_effects([afx.AudioLoop(duration=total_video_dur)])
                    else:
                        bgm = bgm.with_duration(total_video_dur)
                    
                    bgm = bgm.with_effects([afx.AudioFadeOut(3)])
                    # SỬA LỖI TẠI ĐÂY: Thay Volumex bằng MultiplyVolume
                    final_audio_layers.append(bgm.with_effects([afx.MultiplyVolume(1)]))

                # Voice bắt đầu sau khoảng thời gian start_padding im lặng
                silence_voice = AudioClip(lambda t: [0, 0], duration=content_dur, fps=44100)
                combined_voice = CompositeAudioClip([silence_voice, voice.with_start(start_padding)])
                final_audio_layers.append(combined_voice)

                if cta_clip_master and cta_clip_master.audio:
                    final_audio_layers.append(cta_clip_master.audio.with_start(content_dur))

                mixed_audio = CompositeAudioClip(final_audio_layers).with_duration(total_video_dur)

                # Khớp hình ảnh (Speed Up/Down nếu cần)
                content_v = combined_scenes.with_effects([vfx.MultiplySpeed(combined_scenes.duration / content_dur)])
                bg = ColorClip(size=HD_RES, color=(0,0,0), duration=content_dur)
                part_content = CompositeVideoClip([bg, content_v.with_position("center")], size=HD_RES).with_duration(content_dur)

                # Thêm caption bật nảy (Jelly Pop-up)
                if enable_caption and srt_blocks:
                    srt_clips = []
                    y_pos = int(HD_RES[1] * 0.85)
                    for t_start, t_end, text in srt_blocks:
                        dur = t_end - t_start
                        if dur <= 0: dur = 0.1
                        actual_start = t_start + start_padding
                        if actual_start >= content_dur: continue
                        if actual_start + dur > content_dur: dur = content_dur - actual_start
                        
                        try:
                            words = text.split()
                            if not words: continue
                            
                            the_font = os.path.join(BASE_DIR, "fonts", caption_font_name)
                            font_s = caption_size
                            
                            try:
                                pil_font = ImageFont.truetype(the_font, font_s)
                            except:
                                pil_font = ImageFont.load_default()
                                
                            space_w = int(pil_font.getlength(' ') * caption_space_ratio)
                            
                            def get_text_image(text, color, stroke_c=None, stroke_w=0):
                                ascent, descent = pil_font.getmetrics()
                                h = ascent + descent + stroke_w * 2 + 20
                                w = pil_font.getlength(text) + stroke_w * 2 + 30
                                img = Image.new('RGBA', (int(w), h), (0,0,0,0))
                                draw = ImageDraw.Draw(img)
                                
                                x, y = 15, ascent + stroke_w + 10
                                if stroke_c and stroke_w > 0:
                                    draw.text((x, y), text, font=pil_font, fill=color, stroke_width=stroke_w, stroke_fill=stroke_c, anchor="ls")
                                else:
                                    draw.text((x, y), text, font=pil_font, fill=color, anchor="ls")
                                    
                                real_bbox = img.getbbox()
                                if real_bbox:
                                    img = img.crop((real_bbox[0], 0, real_bbox[2], h))
                                return img

                            def add_shadow(img_txt):
                                dx, dy = 4, 4; blur_rad = 3; padd = 10 + blur_rad * 2
                                n_w = img_txt.width + dx + padd
                                n_h = img_txt.height + dy + padd
                                shadow = Image.new('RGBA', (n_w, n_h), (0,0,0,0))
                                black_txt = Image.new('RGBA', img_txt.size, (0, 0, 0, int(255 * 0.9)))
                                black_txt.putalpha(img_txt.getchannel('A').point(lambda p: int(p * 0.9)))
                                sx = padd // 2 + dx; sy = padd // 2 + dy
                                shadow.paste(black_txt, (sx, sy), mask=black_txt)
                                shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur_rad))
                                final_img = Image.new('RGBA', (n_w, n_h), (0,0,0,0))
                                final_img.paste(shadow, (0, 0))
                                final_img.paste(img_txt, (padd // 2, padd // 2), mask=img_txt)
                                return final_img, n_w, n_h

                            word_data = []
                            for w in words:
                                raw_norm = get_text_image(w, caption_color)
                                raw_hl = get_text_image(w, caption_color_hl, 'black', 3)
                                
                                img_norm, w_norm, h_norm = add_shadow(raw_norm)
                                img_hl, w_hl, h_hl = add_shadow(raw_hl)
                                
                                out_w = max(w_norm, w_hl)
                                out_h = max(h_norm, h_hl)
                                
                                cv_norm = Image.new('RGBA', (out_w, out_h), (0,0,0,0))
                                cv_norm.paste(img_norm, ((out_w - w_norm)//2, (out_h - h_norm)//2))
                                
                                cv_hl = Image.new('RGBA', (out_w, out_h), (0,0,0,0))
                                cv_hl.paste(img_hl, ((out_w - w_hl)//2, (out_h - h_hl)//2))
                                
                                word_data.append({'img_norm': cv_norm, 'img_hl': cv_hl, 'w': out_w, 'h': out_h, 'word': w})
                            
                            max_line_w = HD_RES[0] * 0.9
                            lines = []
                            curr_line = []
                            curr_line_w = 0
                            
                            for d in word_data:
                                if curr_line_w + d['w'] > max_line_w and len(curr_line) > 0:
                                    lines.append({'words': curr_line, 'width': curr_line_w - space_w})
                                    curr_line = [d]
                                    curr_line_w = d['w'] + space_w
                                else:
                                    curr_line.append(d)
                                    curr_line_w += d['w'] + space_w
                                    
                            if curr_line:
                                lines.append({'words': curr_line, 'width': curr_line_w - space_w})
                            
                            line_spacing = 15
                            total_h = len(lines) * word_data[0]['h'] + (len(lines)-1)*line_spacing 
                            start_y = y_pos - (total_h // 2)
                            
                            # Tính tổng số ký tự để chia thời gian chữ hiện ra theo cảm giác nhịp điệu tự nhiên của giọng đọc
                            total_chars = sum(len(w_data['word']) for line in lines for w_data in line['words'])
                            current_w_start = actual_start
                            
                            for line_idx, line in enumerate(lines):
                                line_w = line['width']
                                curr_x = (HD_RES[0] - line_w) // 2
                                curr_y = start_y + line_idx * (word_data[0]['h'] + line_spacing)
                                
                                for w_data in line['words']:
                                    w_len = len(w_data['word'])
                                    w_dur = dur * (w_len / total_chars) if total_chars > 0 else dur / len(words)
                                    
                                    w_start = current_w_start
                                    def make_static_clip(arr, c_start, c_dur, pos_x, pos_y):
                                        def f_gen(t): return arr[:, :, :3]
                                        def m_gen(t): return arr[:, :, 3] / 255.0
                                        v = VideoClip(f_gen).with_duration(c_dur)
                                        m = VideoClip(m_gen, is_mask=True).with_duration(c_dur)
                                        return v.with_mask(m).with_start(c_start).with_position((pos_x, pos_y))
                                    
                                    ac_norm = make_static_clip(np.array(w_data['img_norm']), actual_start, dur, curr_x, curr_y)
                                    srt_clips.append(ac_norm)
                                    
                                    ac_hl = make_static_clip(np.array(w_data['img_hl']), w_start, max(w_dur, 0.1), curr_x, curr_y)
                                    srt_clips.append(ac_hl)
                                    
                                    curr_x += w_data['w'] + space_w
                                    current_w_start += w_dur
                                    
                        except Exception as e:
                            print(f"    ⚠️ Bỏ qua caption '{text}' do lỗi: {e}")
                    
                    if srt_clips:
                        part_content = CompositeVideoClip([part_content, *srt_clips], size=HD_RES).with_duration(content_dur)

                final_v = concatenate_videoclips([part_content, cta_clip_master], method="compose") if cta_clip_master else part_content

                # Xuất file Final
                final_v.with_audio(mixed_audio).write_videofile(
                    out_p, 
                    codec="h264_videotoolbox", 
                    audio_codec="aac", 
                    bitrate="8000k", 
                    threads=8,
                    logger="bar"
                )
            
            df_scene.at[s_idx, col_status] = 'Đã hoàn thành'
            save_to_excel(df_scene, excel_path, "scene")
            print(f"  ✅ Part {block_id} DONE.")
            
        except Exception as e:
            print(f"  ❌ Lỗi khi render Part {block_id}: {e}")
        finally:
            for c in clips: c.close()
            if should_delete and os.path.exists(out_p):
                for idx in range(s_idx, e_idx + 1):
                    raw_fn = str(df_scene.at[idx, 'raw_videos']).strip()
                    if raw_fn and raw_fn != 'nan':
                        f_del = os.path.join(p_root, "mastered_scenes", f"{os.path.splitext(raw_fn)[0]}.mp4")
                        if os.path.exists(f_del): os.remove(f_del)
            gc.collect()

    if cta_clip_master: cta_clip_master.close()
