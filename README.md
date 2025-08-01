# 🧠 Taste Backend – Flask Recommendation Engine

This Flask backend powers the cultural recommendation engine for the **Taste** app. It integrates the **Gemini API** for content generation and the **Qloo API** for cultural graph-based recommendations. Users receive highly personalized suggestions based on mood, preferences, archetypes, and even blended group interests.

---

## 🔧 Tech Stack

- **Python** (Flask)
- **Gemini API (Google)** – LLM-based content generation
- **Qloo API** – Cultural similarity engine
- **Firebase Admin SDK** – Preference storage and matching
- **Deployed on Render** – Free tier with 512 MB storage

---

## 📁 Files in This Repo

| File               | Purpose                                      |
|--------------------|----------------------------------------------|
| `app.py`           | Flask app with all backend endpoints         |
| `recommendation.py`| Logic for interacting with Gemini and Qloo   |
| `render.yaml`      | Render deployment config                     |
| `requirements.txt` | Python dependencies                          |

---

## 🚀 Getting Started Locally

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/taste-backend.git
cd taste-backend
```

### 2. Create a Virtual Environment (optional)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Server

```bash
python app.py
```

Your server will run at `http://127.0.0.1:5000`

---

## 🔌 API Endpoints

### `/save-preferences`  
Generate recommendations based on a single user preference in a category.

**Method**: `POST`  
**Payload**:

```json
{
  "preference": "indie rock",
  "activeCategory": "music"
}
```

**Returns**:
- 2 Seed examples for each preference
- 2 groups of 5 recommendations
- Group titles and descriptions

---

### `/get-item-details`  
Fetch structured metadata for a given item.

**Method**: `POST`  
**Payload**:

```json
{
  "name": "Interstellar",
  "category": "movies"
}
```

**Returns**:
- Summary, cast, genre, release year, platforms with icons

---

### `/daily-recommendations`  
Generate activity recommendations based on current mood and preferences.

**Method**: `POST`  
**Payload**:

```json
{
  "mood": "happy",
  "preferences": {
    "music": ["jazz"],
    "books": ["mystery"]
  }
}
```

**Returns**:
- Combined recommendations for relevant activities

---

### `/community-recommendations`  
Recommendations based on user's cultural archetype and selected category.

**Method**: `POST`  
**Payload**:

```json
{
  "archetype": "Taste Explorer",
  "category": "movies"
}
```

**Returns**:
- Items which aligns with particular community people's taste and personality  

---

### `/blend-recommendations`  
Generate group recommendations based on user and friends' preferences.

**Method**: `POST`  
**Payload**:

```json
{
  "userPreferences": {
    "music": ["lofi"]
  },
  "friendPreferences": [
    {
      "music": ["pop"]
    }
  ],
  "selectedActivities": ["music"]
}
```

**Returns**:
- Shared taste recommendations with descriptions

---

### `/mismatch-walkin-their-shoes-gemini`  
Suggest a day-long cultural journey from an opposite community's perspective.

**Method**: `POST`  
**Payload**:

```json
{
  "archetype": "Pop Dreamer"
}
```

**Returns**:
- Music for Morning, Podcasts for afternoon, Movie for Night (which opposite to user's archetype)

---

### `/discover-journey-card-recommendations`  
Get deeper suggestions based on a selected item from the journey cards.

**Method**: `POST`  
**Payload**:

```json
{
  "item": "Bohemian Rhapsody",
  "category": "music"
}
```

**Returns**:
- 1 recommendation with metadata ( e.g movie, movie name, image, director, main cats, platform available, release year )

---

### `/swap_deck-recommendations`  
Return recommendations that intentionally contrast with user's archetype.

**Method**: `POST`  
**Payload**:

```json
{
  "archetype": "Mystic Pulse"
}
```

**Returns**:
- Contrasting items (movie, podcast, book, music, TV) with short factual descriptions

---

## 📡 External Integrations

### 🔷 Gemini API
- Used for preference-based generation
- Descriptive labels
- Archetype and mood interpretation

### 🔶 Qloo API
- Entity graph to fetch similar recommendations
- ID resolution for cultural content

---


