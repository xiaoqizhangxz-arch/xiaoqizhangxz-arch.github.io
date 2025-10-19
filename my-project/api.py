import google.generativeai as genai
import os

try:
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    genai.configure(api_key=api_key)

    print("✅ Successfully connected to the Gemini API.")
    print("Available models supporting 'generateContent':")

    found_pro = False
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(f"- {model.name}")
            if 'gemini-1.5-pro' in model.name or 'gemini-pro' == model.name.split('/')[-1]:
                found_pro = True

    if not found_pro:
        print("\n⚠️ Warning: Could not find 'gemini-pro' or 'gemini-1.5-pro' in the list.")

except Exception as e:
    print(f"❌ An error occurred: {e}")