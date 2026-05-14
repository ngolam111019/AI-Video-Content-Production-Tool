import asyncio
import base64
import os
import pandas as pd
from together import AsyncTogether
from core.config import TOGETHER_API_KEY, MAX_CONCURRENT_REQUESTS

client = AsyncTogether(api_key=TOGETHER_API_KEY)
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

async def generate_single_image(prompt, file_path, index, df, display_name):
    async with semaphore:
        print(f"🎨 [Scene {display_name}] Đang xử lý...")
        try:
            response = await client.images.generate(
                prompt=prompt,
                model="RunDiffusion/Juggernaut-pro-flux",
                width=1280,
                height=768,
                response_format="b64_json"
            )
            image_b64 = response.data[0].b64_json
            if image_b64:
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(image_b64))
                df.at[index, 'status_buoc_2'] = "Success"
                print(f"✅ [Scene {display_name}] Hoàn thành.")
            else:
                df.at[index, 'status_buoc_2'] = "Error: No data returned"
        except Exception as e:
            error_msg = str(e)
            df.at[index, 'status_buoc_2'] = f"Error: {error_msg[:100]}"
            print(f"❌ [Scene {display_name}] Lỗi: {error_msg}")
            if "429" in error_msg:
                await asyncio.sleep(5)

async def _run_image_generation_async(project_path, excel_file):
    image_folder = os.path.join(project_path, "raw_videos")
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)

    df = pd.read_excel(excel_file, sheet_name="scene")
    if 'status_buoc_2' not in df.columns:
        df['status_buoc_2'] = None

    mask = (df['status_buoc_2'].isna()) | (df['status_buoc_2'].astype(str).str.contains('Error', na=False)) | (df['status_buoc_2'] == 'Retry')
    rows_to_process = df[mask]

    if rows_to_process.empty:
        print("✨ Tất cả scene đã 'Success'.")
        return

    print(f"🚀 Cần xử lý {len(rows_to_process)}/{len(df)} scene.")

    tasks = []
    for index, row in rows_to_process.iterrows():
        prompt = row['prompt']
        scene_val = int(row['scene'])
        scene_display = f"{scene_val:03d}" 
        filename = f"{scene_display}.png"
        file_path = os.path.join(image_folder, filename)
        tasks.append(generate_single_image(prompt, file_path, index, df, scene_display))

    try:
        await asyncio.gather(*tasks)
    finally:
        print("\n💾 Đang lưu trạng thái vào file Excel...")
        with pd.ExcelWriter(excel_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name="scene", index=False)
        print("🏁 Đã cập nhật file Excel.")

def step_8_generate_images(project_path, excel_path):
    print(f"\n--- BƯỚC 8: TẠO HÌNH ẢNH TỪ PROMPT ---")
    asyncio.run(_run_image_generation_async(project_path, excel_path))
