import os
import pandas as pd

def get_clean_df(excel_path, sheet_name):
    """Đọc sheet từ file Excel và trả về DataFrame đã chuẩn hóa."""
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
    except Exception as e:
        print(f"❌ Lỗi khi đọc sheet '{sheet_name}': {e}")
        return None
    df.columns = [str(c).strip() for c in df.columns]
    return df

def save_to_excel(df, excel_path, sheet_name):
    """Lưu DataFrame vào sheet chỉ định, giữ nguyên các sheet khác trong workbook."""
    try:
        existing = {}
        if os.path.exists(excel_path):
            try:
                existing = pd.read_excel(excel_path, sheet_name=None)
            except Exception:
                existing = {}
        existing[sheet_name] = df
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            for name, sheet_df in existing.items():
                sheet_df.to_excel(writer, sheet_name=name, index=False)
        return True
    except Exception as e:
        print(f"❌ Lỗi khi lưu sheet '{sheet_name}': {e}")
        return False

def get_project_settings(excel_path):
    """
    Đọc sheet 'setting' và trả về 1 dictionary {key: value}.
    Nếu không có sheet, trẻ về dictionary rỗng để dùng các giá trị mặc định.
    Cột 1 được mong đợi là Key, cột 2 là Value.
    """
    try:
        df = pd.read_excel(excel_path, sheet_name="setting", header=None)
        
        # Bỏ qua dòng Header nếu tên cột được người dùng đặt là "Key"/"Value"
        # Bằng cách lọc các dòng không phải là dict
        settings = {}
        for index, row in df.iterrows():
            if pd.isna(row[0]) or pd.isna(row[1]):
                continue
            key = str(row[0]).strip()
            # Bỏ qua header
            if key.lower() in ['key', 'tên', 'tên biến', 'setting name', 'tên thông số']:
                continue
            val = str(row[1]).strip()
            settings[key] = val
        return settings
    except Exception as e:
        # File không có sheet setting, không cần in lỗi quá nghiêm trọng
        return {}
