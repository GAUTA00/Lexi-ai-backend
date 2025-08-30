from fastapi import FastAPI
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
import requests, os, json, traceback, time
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware



# ===============================
# Load API key and init FastAPI
# ===============================
print("🚀 [DEBUG] Starting FastAPI app...")
load_dotenv()
app = FastAPI()

# Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can restrict to ["http://127.0.0.1:5500"] if using Live Server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("🔑 [DEBUG] Loading Gemini model...")
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.2
)

# ===============================
# Cache system with expiry
# ===============================
cache = {}  # { word: (timestamp, data) }
CACHE_TTL = 600  # 10 minutes in seconds

# ===============================
# Pydantic model
# ===============================
class WordRequest(BaseModel):
    word: str

# ===============================
# Gemini API Call
# ===============================
def call_gemini(word: str):
    prompt = f"""
    Give me the definition, synonyms, and antonyms of the word "{word}".
    Return ONLY valid JSON in this format (no markdown, no explanation):
    {{
      "definition": "...",
      "synonyms": ["..."],
      "antonyms": ["..."]
    }}
    """
    print(f"🔍 [DEBUG] Sending prompt to Gemini for word: {word}")
    response = llm.invoke(prompt).content.strip()   # ✅ invoke instead of predict
    print(f"✅ [DEBUG] Gemini raw response: {response[:200]}...")

    # Remove Markdown fences if present
    if response.startswith("```"):
        print("⚠️ [DEBUG] Gemini returned Markdown, cleaning it...")
        response = response.strip("`")
        if response.startswith("json"):
            response = response[4:].strip()
        response = response.strip()

    try:
        data = json.loads(response)
        print(f"✅ [DEBUG] Parsed Gemini JSON successfully for '{word}'")
    except json.JSONDecodeError as e:
        print("❌ [ERROR] JSON parsing failed:", e)
        data = {"definition": response, "synonyms": [], "antonyms": []}

    return {**data, "source": "gemini"}

# ===============================
# Datamuse Fallback
# ===============================
def call_datamuse(word: str):
    print(f"⚠️ [DEBUG] Falling back to Datamuse for: {word}")
    try:
        synonyms = requests.get(f"https://api.datamuse.com/words?rel_syn={word}").json()
        antonyms = requests.get(f"https://api.datamuse.com/words?rel_ant={word}").json()
    except Exception as e:
        print("❌ [ERROR] Datamuse request failed:", e)
        synonyms, antonyms = [], []

    result = {
        "definition": f"Basic meaning of {word} (Datamuse fallback)",
        "synonyms": [w["word"] for w in synonyms],
        "antonyms": [w["word"] for w in antonyms],
        "source": "datamuse"
    }
    print(f"✅ [DEBUG] Datamuse result for '{word}': {len(result['synonyms'])} synonyms, {len(result['antonyms'])} antonyms")
    return result

# ===============================
# Word Lookup Endpoint
# ===============================
@app.post("/lookup")
async def lookup_word(req: WordRequest):
    word = req.word.lower()
    now = time.time()

    # Check cache
    if word in cache:
        ts, result = cache[word]
        if now - ts < CACHE_TTL:
            print(f"♻️ [DEBUG] Returning cached result for: {word}")
            return result
        else:
            print(f"🗑️ [DEBUG] Cache expired for: {word}, refreshing...")

    # Try Gemini first
    try:
        result = call_gemini(word)
        cache[word] = (now, result)
        print(f"✅ [DEBUG] Stored Gemini result in cache for '{word}'")
        return result
    except Exception as e:
        print("❌ [ERROR] Gemini call failed:")
        traceback.print_exc()

    # Fallback to Datamuse
    result = call_datamuse(word)
    cache[word] = (now, result)
    print(f"✅ [DEBUG] Stored Datamuse result in cache for '{word}'")
    return result
