import subprocess

def get_audio_duration_ffprobe(path):
    """Trả về thời lượng audio (giây) dùng ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(str(res.stdout).strip())
    except Exception:
        return 0.0
