import requests
import os
from dotenv import load_dotenv

# بارگذاری فایل .env
load_dotenv()

# تنظیم کلید API (اکیداً از محیط variable خوانده شود)
api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    print("❌ خطا: متغیر DEEPSEEK_API_KEY تنظیم نشده است.")
    exit(1)

url = "https://api.deepseek.com/models"
headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {api_key}"
}

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # بررسی خطاهای HTTP
    
    data = response.json()
    print("✅ لیست مدل‌های فعال DeepSeek:")
    print("-" * 40)
    
    for model in data.get("data", []):
        print(f"🆔 Model ID: {model.get('id')}")
        print(f"👤 Owner: {model.get('owned_by')}")
        print(f"📌 Object: {model.get('object')}")
        print("-" * 40)
        
except requests.exceptions.RequestException as e:
    print(f"❌ خطا در ارتباط با API: {e}")
except Exception as e:
    print(f"❌ خطای ناشناخته: {e}")
