import os
import re

def time_to_seconds(t_str):
    try:
        t_str = t_str.replace(',', '.')
        parts = t_str.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return int(h)*3600 + int(m)*60 + float(s)
        return 0.0
    except: return 0.0

def seconds_to_srt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def format_timestamp(seconds):
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"

def process_and_shift_srt(srt_path, offset_seconds, start_index):
    """Đẩy mốc thời gian và đánh lại số thứ tự block SRT liên tục"""
    if not os.path.exists(srt_path): return [], start_index
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    blocks = re.split(r'\n\s*\n', content)
    processed_blocks = []
    current_idx = start_index

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 2:
            time_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})', lines[1])
            if time_match:
                start_sec = time_to_seconds(time_match.group(1)) + offset_seconds
                end_sec = time_to_seconds(time_match.group(2)) + offset_seconds
                new_block = f"{current_idx}\n{seconds_to_srt_time(start_sec)} --> {seconds_to_srt_time(end_sec)}\n" + "\n".join(lines[2:])
                processed_blocks.append(new_block)
                current_idx += 1
                
    return processed_blocks, current_idx

def parse_srt_to_word_timeline(srt_path):
    """Chuyển SRT thành timeline các từ (start/end) để đồng bộ với script."""
    if not os.path.exists(srt_path):
        return []
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    blocks = re.split(r'\n\s*\n', content)
    timeline = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue
        match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
        if not match:
            continue
        start = time_to_seconds(match.group(1))
        end = time_to_seconds(match.group(2))
        text = " ".join(lines[2:]).strip()
        words = re.findall(r'\w+', text)
        if not words:
            continue
        per = (end - start) / len(words) if len(words) > 0 else 0
        for i in range(len(words)):
            w_start = start + i * per
            w_end = start + (i + 1) * per
            timeline.append({"start": w_start, "end": w_end})
    return timeline
