import google.generativeai as genai

# put your API key here
API_KEY = "AIzaSyAW-zGwJbhsa2REJDUU7nahKA2h70hkN30"

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash")

prompt = "Give me definition, synonyms, and antonyms of the word 'happy' in JSON format"

response = model.generate_content(prompt)

print(response.text)
