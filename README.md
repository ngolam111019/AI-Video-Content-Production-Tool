# Dự án AutoVideo

Dự án **AutoVideo** là một hệ thống tự động hóa quá trình sản xuất video (Faceless Video / Youtube Automation) dựa trên kịch bản (script) và dữ liệu được cấu hình sẵn trong file Excel.

Hệ thống cung cấp một pipeline hoàn chỉnh từ việc tạo nội dung (âm thanh, hình ảnh qua API) cho đến việc render và ghép nối video cuối cùng thành một sản phẩm hoàn chỉnh.

## 1. Luồng xử lý chính (Pipeline)

Quy trình hoạt động được chia làm nhiều bước, được thiết kế theo một 파이프라인 (pipeline) tuần tự:

1. **Sinh âm thanh và phụ đề (Step 9 - Audio & SRT Generation)**:
   - Dựa vào kịch bản (sheet `script` hoặc `hook` trong Excel).
   - Gọi API (Vimix / ElevenLabs) để tạo giọng đọc (TTS - Text-to-Speech).
   - Trả về và tải xuống các file `.mp3` và `.srt` (phụ đề) chia theo từng block (đoạn).

2. **Sinh hình ảnh (Step 8 - Image Generation)**:
   - Đọc dữ liệu từ sheet `scene` trong Excel.
   - Gọi API (Together AI - model `RunDiffusion/Juggernaut-pro-flux`) dựa vào các `prompt` để tự động tạo ra hình ảnh cho từng cảnh (scene) lưu vào thư mục `raw_videos`.

3. **Chuẩn bị và đồng bộ dữ liệu (Step 2 - Data Preparation)**:
   - Đồng bộ thời lượng âm thanh (`thời gian audio`) vào sheet `script`.
   - Tính toán và đồng bộ timeline (start_time, end_time, read_time) cho sheet `scene` dựa trên file SRT tương ứng của từng block.
   - Thêm thời gian đệm (padding) lúc bắt đầu và kết thúc video.

4. **Render Pacing - Dựng nhịp độ (Step 3 - Render)**:
   - Cắt ghép/tùy chỉnh các video/hình ảnh thô (raw) cho khớp với thời lượng đã tính toán ở bước 2.
   - Tạo ra các đoạn video thô cơ bản để chuẩn bị cho bước tiếp theo.

5. **Master Part - Gắn hiệu ứng (Step 4 - Master Parts Combined)**:
   - Render từng phần video với đầy đủ các lớp (layers): Video nền, Audio, Text (phụ đề), Call-to-action (CTA).
   - Tạo hiệu ứng karaoke cho chữ (word-by-word highlight).

6. **Audio Processing - Xử lý âm thanh tổng (Step 5)**:
   - (Tuỳ chọn) Gộp và chuẩn hóa các luồng âm thanh hoặc tạo thêm nhạc nền nếu cần.

7. **Final Merge - Xuất video cuối cùng (Step 6)**:
   - Gộp tất cả các video master part lại với nhau thành một video hoàn chỉnh duy nhất.

8. **Chuẩn hóa Asset (Step 7)**:
   - Format lại các tệp tài nguyên đầu vào để hệ thống dễ dàng xử lý mà không bị lỗi tương thích định dạng.

## 2. Kiến trúc và Cấu trúc dự án (Mới)

Dự án được tổ chức theo chuẩn **Modular (Microservice-oriented)**, tách biệt các Domain Logic để dễ bảo trì, mở rộng và sẵn sàng dockerize hoặc đưa lên server:

- **`core/`**: Chứa các cấu hình hệ thống, API keys, các thông số tĩnh (`config.py`).
- **`services/`**: Các service lõi để chạy pipeline.
  - **`data_prep/`**: Chuẩn bị, tính toán, map timeline dữ liệu giữa excel, âm thanh và phụ đề.
  - **`media_gen/`**: Giao tiếp với External APIs (Together AI, Vimix) để sinh assets (ảnh, audio).
  - **`video_engine/`**: Lõi dựng video, xử lý render ffmpeg/moviepy, gắn phụ đề, hiệu ứng, nối file.
  - **`audio_engine/`**: Quản lý và xử lý trộn âm thanh riêng biệt.
- **`utils/`**: Các thư viện hàm tiện ích dùng chung (đọc ghi Excel, đo thời gian file media, parse file SRT).
- **`main.py`**: Entry-point của ứng dụng, chịu trách nhiệm nhận lệnh điều khiển và điều phối các services.

## 3. Công nghệ sử dụng
- **Ngôn ngữ**: Python
- **Thư viện chính**: `pandas` (xử lý dữ liệu Excel), `requests` / `aiohttp` / `together` (tương tác API), xử lý video qua CLI (`ffmpeg`) hoặc thư viện `moviepy`.
- **API Tích hợp**:
  - Together AI (Tạo ảnh Juggernaut-pro-flux).
  - Vimix / Elevenlabs (Tạo giọng đọc chuẩn tự nhiên + SRT).

## 4. Hướng dẫn cài đặt (Quick Start)

Dự án yêu cầu cài đặt **Python 3.10+** và **FFmpeg** trên hệ thống.

### 4.1. Thiết lập môi trường
Cài đặt thư viện bằng `pip`:
```bash
# Tạo môi trường ảo (Khuyến nghị)
python3 -m venv .venv
source .venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt
```

### 4.2. Cấu hình API Keys
Tạo một file `.env` từ file mẫu `.env.example`:
```bash
cp .env.example .env
```
Sau đó mở file `.env` và điền các khóa API của bạn (Together AI, Vimix).

### 4.3. Cấu trúc dữ liệu yêu cầu
Để hệ thống hoạt động, thư mục cấp trên (chứa dự án) cần có thư mục `videos` tổ chức theo dự án như sau:
```text
videos/
└── [Tên Dự Án]/
    ├── [Tên Dự Án].xlsx   # File kịch bản cấu hình
    └── raw_videos/        # (Tùy chọn) Chứa video hoặc ảnh gốc nếu tự thiết kế
```

### 4.4. Chạy chương trình
Khởi chạy entry-point chính:
```bash
python main.py
```
Giao diện dòng lệnh (CLI) sẽ hiển thị menu để bạn chọn các bước xử lý (Tạo âm thanh, tạo ảnh, render, master, final merge...).
