import pandas as pd
import uuid
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FOLDER = os.path.join(BASE_DIR, "converted")
UPLOAD_FOLDER = BASE_DIR

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def normalize_json(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()

        if not raw:
            raise Exception("JSON file is empty")
        data = json.loads(raw)

        if isinstance(data, list):
            return pd.json_normalize(data)

        if isinstance(data, dict):

            for key, value in data.items():
                if isinstance(value, list):
                    return pd.json_normalize(value)

            return pd.json_normalize([data])

    except json.JSONDecodeError:

        try:
            return pd.read_json(file_path, lines=True)
        except Exception:
            raise Exception("Invalid or corrupted JSON file")

def read_file(file_path):
    ext = file_path.split(".")[-1].lower()

    if ext in ["xlsx", "xls"]:
        df = pd.read_excel(file_path)

    elif ext == "xlsb":
        df = pd.read_excel(file_path, engine="pyxlsb")

    elif ext == "json":
        df = normalize_json(file_path)

    elif ext in ["csv", "txt"]:
        try:
            df = pd.read_csv(
                file_path,
                engine="python",
                sep=None,
                on_bad_lines="skip"
            )
        except:
            df = pd.read_csv(
                file_path,
                engine="python",
                sep=r"\s+",
                on_bad_lines="skip",
                header=None
            )

    else:
        raise Exception("Unsupported file format")

    return df

def save_converted_file(df, output_format):
    unique_id = str(uuid.uuid4())
    output_file = f"{unique_id}.{output_format}"
    output_path = os.path.join(OUTPUT_FOLDER, output_file)

    if output_format == "csv":
        df.to_csv(output_path, index=False)

    elif output_format == "xlsx":
        df.to_excel(output_path, index=False)

    elif output_format == "json":
        df.to_json(output_path, orient="records", indent=2)

    elif output_format == "txt":
        df.to_csv(output_path, index=False)

    else:
        raise Exception("Unsupported output format")

    return output_file

def convert_file(file_path, output_format):
    df = read_file(file_path)
    converted_filename = save_converted_file(df, output_format)
    return converted_filename

if __name__ == "__main__":
    
    files = [
        r"C:\Users\T.Vimal Raj\Downloads\sample.txt",
    ]

    target_format = "xlsx"

    print("\n UNIVERSAL FILE CONVERSION STARTED...\n")

    for file in files:
        try:
            output = convert_file(file, target_format)
            print(f"Converted: {file} → {output}")
        except Exception as e:
            import traceback
            print(f"Failed: {file} → {str(e)}")
            print("Full traceback:")
            print(traceback.format_exc())

    print("\n ALL FILES CONVERTED SUCCESSFULLY!\n")
