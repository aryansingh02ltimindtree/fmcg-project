#Working sample gemini 2.5 flash code

# from langchain_google_genai import ChatGoogleGenerativeAI

# def main():
#     print("--- Gemini API Quick Test ---")
#     api_key = input("Enter your Gemini API Key: ").strip()

#     if not api_key:
#         print("❌ API key cannot be empty.")
#         return

#     try:
#         model = ChatGoogleGenerativeAI(
#             model="gemini-2.5-flash",
#             google_api_key=api_key
#         )
#         print("✅ Model initialized successfully!")

#         user_prompt = input("\nEnter your prompt: ")
#         user_prompt="Parse this json and give insights, dont invent numbers only give factual insights:"+user_prompt
#         response = model.invoke(user_prompt)

#         print("\n--- GEMINI RESPONSE ---")
#         print(response.content)
#         print("-----------------------")

#     except Exception as e:
#         print(f"❌ Error: {e}")

# if __name__ == "__main__":
#     main()


#Working code with gemini api key
# from typing import Union
# import json
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_core.prompts import ChatPromptTemplate


# # === New helper function you can import and call from main.py ===
# def generate_gemini_insights(api_key: str, payload: Union[dict, str]) -> str:
#     """
#     Given an API key and a JSON payload (dict or JSON string),
#     returns Gemini's insight text using a strict prompt template.
#     """
#     # 1) Initialize model (unchanged)
#     model = ChatGoogleGenerativeAI(
#         model="gemini-2.5-flash",
#         google_api_key=api_key
#     )

#     # 2) Make sure we have a JSON string
#     if isinstance(payload, dict):
#         payload_str = json.dumps(payload, ensure_ascii=False)
#     else:
#         payload_str = payload.strip()

#     # 3) Prompt template (added)
#     # Keep it strict: use only facts/numbers from the JSON, no invention.
#     prompt = ChatPromptTemplate.from_messages(
#         [
#             (
#                 "system",
#                 (
#                     "You are an FMCG insights writer. "
#                     "ONLY use numbers and labels present in the provided JSON. "
#                     "Do not invent or estimate any values. "
#                     "Write 3-4 concise, facts (45<=words each). "
#                     "No marketing fluff, no new numbers."
#                 ),
#             ),
#             (
#                 "human",
#                 (
#                     "Parse the JSON below and give factual insights only.\n"
#                     "JSON:\n```json\n{json_block}\n```"
#                 ),
#             ),
#         ]
#     )

#     messages = prompt.format_messages(json_block=payload_str)

#     # 4) Invoke model and return raw text (unchanged behavior)
#     response = model.invoke(messages)
#     return response.content


# # === Quick local test runner (optional) ===
# def main():
#     print("--- Gemini API Quick Test ---")
#     api_key = input("Enter your Gemini API Key: ").strip()
#     if not api_key:
#         print("❌ API key cannot be empty.")
#         return

#     try:
#         # In your app, you'll call generate_gemini_insights(api_key, payload_from_main)
#         # Here we accept a JSON string for quick testing.
#         user_json = input("\nPaste your JSON payload: ").strip()

#         # Call the function with whatever JSON your main.py assembles
#         insights_text = generate_gemini_insights(api_key, user_json)

#         print("\n--- GEMINI RESPONSE ---")
#         print(insights_text)
#         print("-----------------------")

#     except Exception as e:
#         print(f"Error: {e}")


# if __name__ == "__main__":
#     main()







import re
import io
from typing import Union
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate


# === New helper function you can import and call from main.py ===
def generate_gemini_insights(api_key: str, payload: Union[dict, str]) -> str:
    """
    Given an API key and a JSON payload (dict or JSON string),
    returns Gemini's insight text using a strict prompt template.
    """
    # 1) Initialize model (unchanged)
    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key
    )

    # 2) Make sure we have a JSON string
    if isinstance(payload, dict):
        payload_str = json.dumps(payload, ensure_ascii=False)
    else:
        payload_str = payload.strip()

    # 3) Prompt template (added)
    # Keep it strict: use only facts/numbers from the JSON, no invention.
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are an FMCG insights writer. "
                    "ONLY use numbers and labels present in the provided JSON. "
                    "Do not invent or estimate any values. "
                    "Write 3-4 concise, facts (45<=words each). "
                    "No marketing fluff, no new numbers."
                ),
            ),
            (
                "human",
                (
                    "Parse the JSON below and give factual insights only.\n"
                    "JSON:\n```json\n{json_block}\n```"
                ),
            ),
        ]
    )

    messages = prompt.format_messages(json_block=payload_str)
    import re

    # 4) Invoke model and return raw text (unchanged behavior)
    response = model.invoke(messages)
    clean_text = re.sub(r'\n+', ' ', response.content)
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', clean_text)
    sentences = [s.strip() for s in sentences if s.strip()]

    return sentences


# === Quick local test runner (optional) ===
def main():
    print("--- Gemini API Quick Test ---")
    api_key = input("Enter your Gemini API Key: ").strip()
    if not api_key:
        print("❌ API key cannot be empty.")
        return

    try:
        # In your app, you'll call generate_gemini_insights(api_key, payload_from_main)
        # Here we accept a JSON string for quick testing.
        user_json = input("\nPaste your JSON payload: ").strip()

        # Call the function with whatever JSON your main.py assembles
        insights_text = generate_gemini_insights(api_key, user_json)

        print("\n--- GEMINI RESPONSE ---")
        print(insights_text)
        print("-----------------------")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()


