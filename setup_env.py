import os

def create_env():
    print("\n🚀 Amir CLI Environment Setup")
    print("===============================")
    print("This script will generate a .env file for your API keys.\n")

    gemini = input("Enter your GEMINI_API_KEY (Leave empty if none): ").strip()
    
    with open(".env", "w") as f:
        if gemini:
            f.write(f'GEMINI_API_KEY="{gemini}"\n')
            
    print("\n✅ .env file created successfully!")
    print("You can edit it manually anytime.")

if __name__ == "__main__":
    create_env()
