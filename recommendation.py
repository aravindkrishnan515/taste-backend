import re
import google.generativeai as genai
import requests
import json
import random
import firebase_admin
import os

from firebase_admin import credentials, firestore

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
QLOO_API_KEY = os.getenv("QLOO_API_KEY")

print("Google API Key is:", GOOGLE_API_KEY)
print("Qloo API Key is:", QLOO_API_KEY)                                 

# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

QLOO_BASE_URL = "https://hackathon.api.qloo.com"

QLOO_Headers = {
    "x-api-key": QLOO_API_KEY
}

ENTITY_TYPE_MAP = {                         
    "movies": "urn:entity:movie",
    "books": "urn:entity:book",
    "travel": "urn:entity:place",
    "podcast":"urn:entity:podcast",
    "videogame":"urn:entity:videogame", 
    "video games":"urn:entity:videogame",
    "tv_show":"urn:entity:tv_show",
    "tv shows":"urn:entity:tv_show",                                                
    "music":"urn:entity:artist",
    "album":"urn:entity:album"
}

# Create a model instance
model = genai.GenerativeModel("gemini-2.5-flash")

# def get_examples(preferences):
#     prompt = f"""
# You are a recommendation system that specializes in Western cultural preferences.

# The user provides their preferences in the following categories: music, movies, food, books, and travel.

# Here is the user's input:
# {json.dumps(preferences, indent=2)}

# Your task:
# - For each input item under a category, generate 2 distinct and culturally relevant recommendations from Western culture.
# - Every time this function is called, return a new set of suggestions (no repetition).
# - Avoid using the same recommendations across different runs or input items.

# Output format (only valid raw JSON, no explanation):
# {{
#   "music": [["example1", "example2"], ["example3", "example4"]],
#   "movies": [["example1", "example2"], ["example3", "example4"]],
#   "books": [["example1", "example2"], ["example3", "example4"]],
#   "podcast": [["example1", "example2"], ["example3", "example4"]],
#   "videogame": [["example1", "example2"], ["example3", "example4"]],
#   "tv_show": [["example1", "example2"], ["example3", "example4"]],
#   "travel": [["example1", "example2"], ["example3", "example4"]],
#   "artist": [["example1", "example2"], ["example3", "example4"]],
#   "albums": [["example1", "example2"], ["example3", "example4"]]
# }}

# ⚠️ Requirements:
# - Categories must match user's input.
# - Each value must be a list of arrays.
# - Each array should have exactly 2 recommendations, related to the corresponding input item.
# - Return only valid JSON. No notes, no markdown, no code blocks.
# """

#     try:
#         response = model.generate_content(
#             prompt,
#             generation_config={
#                 "temperature": 1.3,  # Add randomness
#                 "top_p": 1.0,
#                 "top_k": 40
#             }
#         )

#         # Clean and extract JSON
#         json_text = response.text.strip()

#         if "```json" in json_text:
#             json_text = json_text.split("```json")[-1].split("```")[0].strip()
#         elif "```" in json_text:
#             json_text = json_text.split("```")[-2].strip()

#         print("Cleaned JSON text:", json_text)
#         result = json.loads(json_text)

#         # Ensure structure integrity
#         for category in result:
#             if not isinstance(result[category], list):
#                 result[category] = []

#         return result

#     except Exception as e:
#         print("Error parsing JSON:", e)
#         print("Raw response:", response.text)

#         # Fallback empty results
#         fallback = {}
#         if preferences:
#             for category in preferences:
#                 fallback[category] = [["No recommendation available", "Try again later"]
#                                       for _ in preferences[category]]

#         return fallback

import json

def get_single_example(category, preference):
    prompt = f"""
You are a recommendation system that specializes in Western cultural preferences.

The user has selected one preference in the category "{category}":
- Preference: "{preference}"

Your task:
- Generate exactly 2 distinct and culturally relevant recommendations from Western culture that relate to this single input preference.
- Make sure these are fresh and not repeated across runs.
- Do NOT repeat results from any previous call.

Return only **valid raw JSON**, no notes or explanations.

Output format:
{{
  "recommendations": ["example1", "example2"]
}}

⚠️ Requirements:
- The key must be exactly "recommendations"
- Value must be an array of two unique items
- No markdown, no code blocks, no extra formatting
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 1.3,  # Add randomness
                "top_p": 1.0,
                "top_k": 40
            }
        )

        json_text = response.text.strip()

        # Clean and extract JSON
        if "```json" in json_text:
            json_text = json_text.split("```json")[-1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[-2].strip()

        print("Cleaned JSON text:", json_text)
        result = json.loads(json_text)

        # Validate structure
        if not isinstance(result.get("recommendations"), list) or len(result["recommendations"]) != 2:
            return { "recommendations": ["Invalid", "Try again"] }

        return result

    except Exception as e:
        print("Error parsing JSON:", e)
        print("Raw response:", response.text if 'response' in locals() else '')

        return {
            "recommendations": ["No recommendation", "Try again later"]
        }

    
def find_entity_id(query, entity_type):
    """Search for an entity by name and return its entity_id"""
    response = requests.get(
        f"{QLOO_BASE_URL}/search",
        headers={"x-api-key": QLOO_API_KEY},
        params={
            "query": query,
            "filter.type": entity_type,
            "limit": 1
        }
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    if results:
        return results[0].get("entity_id")
    return None

def map_names_to_entity_ids(recommendation_json):
    """
    Convert recommendation names to entity_ids, preserving nested list structure.
    """
    entity_id_json = {}

    for category, nested_list in recommendation_json.items():
        print(category)
        entity_type = ENTITY_TYPE_MAP.get(category)
        print(entity_type)
        if not entity_type:
            continue

        converted_category = []
        for sublist in nested_list:
            converted_sublist = []
            for name in sublist:
                entity_id = find_entity_id(name, entity_type)
                converted_sublist.append(entity_id)
            converted_category.append(converted_sublist)

        entity_id_json[category] = converted_category

    return entity_id_json



def fetch_individual_recommendation(entity_id, target_entity_type, take):
    """
    Fetch structured recommendations (name and image) for a single entity ID.
    """
    try:
        params = {
            "filter.type": target_entity_type,
            "signal.interests.entities": entity_id,
            "take": take
        }
        response = requests.get(
            f"{QLOO_BASE_URL}/v2/insights",
            headers=QLOO_Headers,
            params=params
        )
        response.raise_for_status()
        data = response.json()

        entities = data.get("results", {}).get("entities", [])

        return [
            {
                "name": item.get("name", "Unknown"),
                "image": item.get("properties", {}).get("image", {}).get("url", "")
            }
            for item in entities
        ]

    except Exception as e:
        print(f"Error for entity {entity_id}: {e}")
        return []
    
def get_recommendations(target_category, entity_id_json, take=3):
    """
    For a given target category (e.g., 'movies'),
    fetch recommendations grouped by each entity_id, and return a list of lists of structured movie data.
    """
    if target_category not in ENTITY_TYPE_MAP:
        raise ValueError(f"Invalid category: {target_category}")

    target_entity_type = ENTITY_TYPE_MAP[target_category]
    grouped_recommendations = []

    for nested_lists in entity_id_json.values():
        for sublist in nested_lists:
            for entity_id in sublist:
                if entity_id and not entity_id.startswith("NOT_FOUND"):
                    recs = fetch_individual_recommendation(entity_id, target_entity_type, take)
                    if recs:
                        grouped_recommendations.append(recs)

    return {target_category: grouped_recommendations}



def get_item_details(category: str, name: str):
    
    category = category.lower()

    prompt = f"""
        You are a structured knowledge assistant.

        The user has selected a {category}. The title is:
        "{name}"

        Give detailed metadata in the following JSON format.

        IMPORTANT:
        - In "platforms_available", return only platforms whose official icon image URLs are publicly accessible and not under maintenance.
        - If a platform's icon URL is not reachable (e.g., returns an error page, or "under maintenance"), DO NOT include that platform.
        - Each item in "platforms_available" must include:
        {{
            "name": "Platform Name",
            "icon_url": "https://... (must work when visited in a browser)"
        }}

        Return valid JSON only. Do not include any notes, explanation, or markdown.

        For movies:
        {{
        "name": "...",
        "release_year": ...,
        "director": "...",
        "main_cast": ["...", "..."],
        "genre": "...",
        "platforms_available": [{{ "name": "Netflix", "icon_url": "..." }}, ...]
        }}

        For books:
        {{
        "name": "...",
        "author": "...",
        "release_year": ...,
        "genre": "...",
        "platforms_available": [{{ "name": "Amazon", "icon_url": "..." }}, ...]
        }}

        For podcasts:
        {{
        "name": "...",
        "host": "...",
        "release_year": ...,
        "topics": "...",
        "platforms_available": [{{ "name": "Spotify", "icon_url": "..." }}, ...]
        }}

        For videogames:
        {{
        "name": "...",
        "developer": "...",
        "release_year": ...,
        "platforms": ["PC", "PS5", ...],
        "genre": "...",
        "platforms_available": [{{ "name": "Steam", "icon_url": "..." }}, ...]
        }}

        For TV shows:
        {{
        "name": "...",
        "creator": "...",
        "seasons": ...,
        "main_cast": ["...", "..."],
        "genre": "...",
        "platforms_available": [{{ "name": "Netflix", "icon_url": "..." }}, ...]
        }}

        For artists:
        {{
        "name": "...",
        "genre": "...",
        "platforms_available": [{{ "name": "YouTube", "icon_url": "..." }}, ...]
        }}

        For travel:
        {{
        "name": "...",
        "country": "...",
        "best_time_to_visit": "...",
        "top_attractions": ["...", "..."],
        "travel_type": "...", 
        "platforms_available": [{{ "name": "TripAdvisor", "icon_url": "..." }}, ...]
        }}

        Respond with only valid JSON. No explanation, no markdown, no notes.
        """


    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Remove ```json or ``` if present
        if "```json" in raw:
            raw = raw.split("```json")[-1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].strip()

        return json.loads(raw)

    except Exception as e:
        print(f"Error fetching Gemini details for {name} ({category}):", e)
        return {
            "name": name,
            "error": "Failed to retrieve detailed info. Please try again."
        }

def get_activity_recommendations_by_mood(mood: str) -> dict:
    """
    Based on the user's current mood, return a set of different activity recommendations
    from Western culture across suitable categories, with varied results on each call.
    """

    prompt = f"""
You are a recommendation system that specializes in Western cultural preferences.

A user is currently feeling **{mood}**.

From the following activity types:
- movies
- books
- podcast
- videogame
- tv_show
- travel
- artist
- music

Select the activity types that best match the user's current mood. For each selected activity type, generate **one highly popular and culturally relevant example** from Western culture.

🌀 Each time this prompt is called, return different valid examples. Randomize the selection. Do NOT repeat the same set of outputs across calls.

Return only valid raw JSON in the following format:
{{
  "movies": "Example movie",
  "books": "Example book",
  "music": "Example song",
  "podcast": "Example podcast",
  "videogame": "Example game",
  "tv_show": "Example TV show",
  "travel": "Example destination",
  "artist": "Example artist"
}}

⚠️ Requirements:
- Include only activity types relevant to the mood.
- Return at least **two activity types**.
- All examples must be popular and recognizable in Western culture.
- Do NOT include any explanation, commentary, or markdown. Only raw JSON output.
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 1.2,  # Encourage diversity
                "top_p": 1.0,
                "top_k": 40
            }
        )

        json_text = response.text.strip()

        # Handle code blocks if present
        if json_text.startswith("```json"):
            json_text = json_text.split("```json")[-1].split("```")[0].strip()
        elif json_text.startswith("```"):
            json_text = json_text.split("```")[-1].strip()

        result = json.loads(json_text)

        if isinstance(result, dict) and len(result) >= 2:
            return result
        else:
            raise ValueError("Less than 2 valid activity types returned")

    except Exception as e:
        print("Error calling Gemini or parsing response:", e)
        return {
            "error": "Failed to fetch recommendations from Gemini",
            "details": str(e)
        }
    
def get_genre_based_examples(filtered_preferences: dict) -> dict:

    prompt = f"""
You are a cultural recommendation system that specializes in Western culture (e.g., US, UK, Europe).

The user has the following genre preferences under each activity category:

{json.dumps(filtered_preferences, indent=2)}

Your task:
- For each genre under each activity, recommend exactly ONE **highly popular** and **widely recognized** example from Western culture.
- Randomly select a different example each time this request is made.
- Avoid repeating the same examples across different calls.

Output format:
- The number of examples must match the number of genres per activity.
- Return only a valid JSON object like this:
{{
  "music": ["Jazz example", "Rock example"],
  "books": ["Mystery example"]
}}

⚠️ Requirements:
- No explanation or commentary.
- Do NOT use markdown or code formatting.
- Output only a raw JSON object.
"""


    response = model.generate_content(prompt)
    text = response.text.strip()

    # Clean up any markdown or code block formatting
    if text.startswith("```json"):
        text = text[len("```json"):].strip("`\n ")
    elif text.startswith("```"):
        text = text[3:].strip("`\n ")

    # Extract JSON from the response (handles if extra text included)
    try:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            json_text = match.group()
            return json.loads(json_text)
        else:
            # fallback to direct json.loads if no extra text
            return json.loads(text)
    except Exception as e:
        print("Failed to parse Gemini response as JSON:", e)
        print("Raw response:", text)
        return {}
    
def find_entity_id(query, entity_type):
    """Search Qloo for an entity name and return its entity_id."""
    try:
        if not query or not query.strip():
            print(f"[WARN] Empty query received for type '{entity_type}'")
            return None

        response = requests.get(
            f"{QLOO_BASE_URL}/search",
            headers={"x-api-key": QLOO_API_KEY},
            params={
                "query": query.strip(),
                "filter.type": entity_type,
                "limit": 1
            },
            timeout=10  # Always add a timeout to avoid hanging
        )
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        if results and "entity_id" in results[0]:
            entity_id = results[0]["entity_id"]
            if entity_id and isinstance(entity_id, str):
                return entity_id

        print(f"[WARN] No valid entity_id found for query '{query}' ({entity_type})")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request error for '{query}' ({entity_type}): {e}")
    except Exception as e:
        print(f"[ERROR] Unexpected error for '{query}' ({entity_type}): {e}")
    
    return None


def merge_and_map_entity_ids(recommendations: dict, preference_examples: dict) -> dict:
    """
    Combine recommendation and preference example names under each activity,
    and map them to their corresponding entity IDs.

    Returns:
        dict: {activity: [entity_id1, entity_id2, ...]}
    """

    combined_ids = {}

    # Merge all keys from both sources
    all_keys = set(recommendations.keys()) | set(preference_examples.keys())

    for category in all_keys:
        entity_type = ENTITY_TYPE_MAP.get(category)
        if not entity_type:
            continue

        names = []

        # Add recommendation if present (as string)
        if category in recommendations and isinstance(recommendations[category], str):
            names.append(recommendations[category])

        # Add preference examples if present (as list)
        if category in preference_examples and isinstance(preference_examples[category], list):
            names.extend(preference_examples[category])

        entity_ids = []
        for name in names:
            entity_id = find_entity_id(name, entity_type)
            entity_ids.append(entity_id)

        combined_ids[category] = entity_ids

    return combined_ids

def get_recommendations_for_activities(entity_id_json, activity_list, take=1):
    all_recommendations = {}

    for category in activity_list:
        if category not in ENTITY_TYPE_MAP:
            print(f"Skipping unsupported category: {category}")
            continue

        entity_ids = entity_id_json.get(category, [])
        if not entity_ids:
            continue

        # Filter out invalid or NOT_FOUND entries
        valid_entity_ids = [eid for eid in entity_ids if eid and not str(eid).startswith("NOT_FOUND")]
        if not valid_entity_ids:
            continue

        target_entity_type = ENTITY_TYPE_MAP[category]

        # Fetch recommendations using combined entity IDs
        recs = fetch_combined_recommendations(valid_entity_ids, target_entity_type, take)
        if recs:
            all_recommendations[category] = recs

    return all_recommendations



def fetch_combined_recommendations(entity_ids, target_entity_type, take=5):
    try:
        # Join entity IDs as comma-separated string
        combined_ids = ",".join(entity_ids)

        params = {
            "filter.type": target_entity_type,
            "signal.interests.entities": combined_ids,
            "filter.popularity.min": 0.80,
            "take": take
        }

        response = requests.get(
            f"{QLOO_BASE_URL}/v2/insights",
            headers=QLOO_Headers,
            params=params
        )
        response.raise_for_status()
        data = response.json()

        entities = data.get("results", {}).get("entities", [])

        return [
            {
                "name": item.get("name", "Unknown"),
                "image": item.get("properties", {}).get("image", {}).get("url", "")
            }
            for item in entities
        ]

    except Exception as e:
        print(f"Error fetching combined recommendations for entity IDs: {e}")
        return []

def get_community_example(community: str, category: str) -> str:
    """
    Returns the name of one randomly selected Western-culture-based example from the given category
    that aligns with the preferences of the specified community.
    Each call is designed to return a different example.
    """

    prompt = f"""
You are a cultural trends expert.

Your task is to identify one specific example from Western culture that matches the interests
of a community.

Community: "{community}"
Category: "{category}"

Constraints:
- The example must belong to the given category.
- It must be well-known or relevant in Western culture (e.g., US, UK, or Europe).
- Each time, randomly select one relevant and culturally aligned example. Avoid repetition.
- Do not explain or add context.
- Do not return anything other than the exact name/title of the example.
- No punctuation, no quotation marks, no lists — only the example name as plain text.

Output format:
[example_name_only]
"""

    try:
        response = model.generate_content(prompt, generation_config={"temperature": 1.1})
        return response.text.strip()
    except Exception as e:
        return f"Error: {str(e)}"


def get_opposite_community_journey_cards(community_type: str) -> dict:

    prompt = f"""
You are a cultural journey assistant.

The user belongs to the following community: "{community_type}".

Your task:
- Choose any random community from the following:
  [
    'Alt Pulse','Lyrical Romantic', 'Culture Hacker', 'Berry Bloom', 'Minimal Spirit', 'Mystic Pulse', 'Pop Dreamer', 
    'Zen Zest', 'Hidden Flame', 'Wander Muse', 'Sunset Rebel', 'Cottage Noir', 'Neon Thinker', 'Kaleido Crafter', 
    'Earth Artisan', 'Retro Soul', 'Cyber Chill', 'Tropic Vibist', 'Hyper Connector', 'Cine Nomad', 'Cloudwalker', 
    'Vintage Flâneur', 'Joy Alchemist', 'Sunkissed Soul']


Then:
- Recommend three culturally fitting and specific items enjoyed by people from that opposite community:
  1. Morning → a music track
  2. Afternoon → a podcast episode
  3. Night → a movie

Instructions:
- Give **real, specific titles** (e.g., actual songs, shows, and films from Western culture)
- Randomize the choosing community and the items on each call
- Do not repeat same communities or items from various outputs

⚠️ Format:
Return only a JSON dictionary in this format:

{{
  "morning": {{
    "content": "Listen to this track from the [Random Archetype]",
    "item": "Real Music Track Title",
    "archetype": "Opposite Archetype"
  }},
  "afternoon": {{
    "content": "Try this show from the [Random Archetype]",
    "item": "Real podcast Title",
    "archetype": "Opposite Archetype"
  }},
  "night": {{
    "content": "Watch this film from the [Random Archetype]",
    "item": "Real Movie Title",
    "archetype": "Opposite Archetype"
  }}
}}

Only return raw JSON. No extra text. No markdown. No explanation.
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Remove code formatting if present
    if text.startswith("```json"):
        text = text[len("```json"):].strip("`\n ")
    elif text.startswith("```"):
        text = text[3:].strip("`\n ")

    try:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            json_text = match.group()
            return json.loads(json_text)
        else:
            return json.loads(text)
    except Exception as e:
        print("Failed to parse Gemini response as JSON:", e)
        print("Raw response:", text)
        return {}
    

def get_examples_for_user_and_friends(user_preferences, co_person_preferences, selected_activities) -> dict:
    
    if not selected_activities:
        raise ValueError("You must provide at least one selected activity.")
    
    activity = selected_activities[0]

    prompt = f"""
        You are a cultural recommendation assistant.

        The user's preferences are:
        {json.dumps(user_preferences, indent=2)}

        The user's friends have the following preferences and relationships:
        {json.dumps(co_person_preferences, indent=2)}

        The user has selected the activity: "{activity}"

        Your task:
        - Analyze all preferences of user and each co-person (not just the selected activity)
        - understand the user's and each co-person's overall taste and personality.
        - Then return one culturally relevant and specific example for the selected activity ("{activity}"):
            - One example that suits the user.
            - One example for each friend (in a list), based on their preferences.

        ⚠️ Return only valid raw JSON like this:
        {{
        "user_preference_example": "One specific title for user",
        "friend_preference_example": [
            "Title for first friend",
            "Title for second friend",
            ...
        ]
        }}

        ⚠️ Do not include markdown, explanation, or commentary. Just the JSON.
            """.strip()

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Remove any accidental markdown or formatting
    if text.startswith("```json"):
        text = text[len("```json"):].strip("`\n ")
    elif text.startswith("```"):
        text = text[3:].strip("`\n ")

    try:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            json_text = match.group()
            return json.loads(json_text)
        else:
            return json.loads(text)
    except Exception as e:
        print("Failed to parse Gemini response as JSON:", e)
        print("Raw response:", text)
        return {}
    
def enrich_recommendations_with_details(recommendations: list, category: str):
    enriched_recommendations = []
    
    for item in recommendations:
        name = item.get("name")
        image = item.get("image")
        
        prompt = f"""
        The user received a {category} recommendation titled: "{name}".

        Your task is to return valid JSON with:
        - A short summary (within 2 lines)
        - An appropriate rating ( e.g for movies from imdb, books from Goodreads)
        - Cost estimate ("Free", "Paid")

        Return response strictly as JSON:
        {{
          "summary": "Brief description",
          "rating": "4.2",
          "cost": "$$"
        }}
        """

        try:
            response = model.generate_content(prompt)
            text = response.text.strip()

            if text.startswith("```json"):
                text = text[len("```json"):].strip("`\n ")
            elif text.startswith("```"):
                text = text[3:].strip("`\n ")

            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                json_text = match.group()
                details = json.loads(json_text)
            else:
                details = json.loads(text)
                
            enriched_recommendations.append({
                "name": name,
                "image": image,
                "summary": details.get("summary", "Great recommendation for you"),
                "rating": details.get("rating", "4.0"),
                "cost": details.get("cost", "$$")
            })
            
        except Exception as e:
            print(f"Failed to enrich {name}:", e)
            enriched_recommendations.append({
                "name": name,
                "image": image,
                "summary": "Great recommendation for you",
                "rating": "4.0",
                "cost": "$$"
            })
    
    return enriched_recommendations

def get_contrasting_examples(archetype):
    """
    Given a taste archetype, call Gemini API and return contrasting recommendations
    across movie, podcast, book, music, and TV.
    """

    prompt = f"""
You are a taste contrast engine. Your job is to recommend cultural content that **strongly contrasts**
with the taste archetype provided. The contrast should be in tone, worldview, energy, or theme.

Archetype: "{archetype}"

Generate a **different, meaningful, and randomly selected** example in each of the following categories:
1. Movies
2. Podcast
3. Books
4. Music (artist or album)
5. TV Show

Guidelines:
- Do NOT repeat examples from previous outputs.
- Vary genres, time periods, and cultural backgrounds.
- Avoid mainstream picks unless they’re uniquely contrasting.
- Ensure each item clearly contrasts with the given archetype in mood, values, or storytelling.

Return ONLY valid JSON in this exact format — no explanations, markdown, or extra text:

{{
  "movies": "Movie Title",
  "podcast": "Podcast Title",
  "books": "Book Title",
  "music": "Music Artist or Album",
  "tv_show": "TV Show Title"
}}
"""


    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Clean markdown formatting like ```json ... ```
        cleaned = re.sub(r"^```json|^```|```$", "", text.strip(), flags=re.MULTILINE).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw_text": text, "error": "Failed to parse JSON"}

    except Exception as e:
        return {"error": str(e)}

def map_examples_to_entity_ids(contrast_examples):
    """
    Takes a dictionary of contrast examples (movie, podcast, etc.)
    and returns a new dictionary mapping each category to its entity_id.
    """
    entity_ids = {}

    for category, example_name in contrast_examples.items():
        # Normalize category name to match ENTITY_TYPE_MAP keys
        normalized_category = category.strip().lower()
        
        entity_type = ENTITY_TYPE_MAP.get(normalized_category)
        if not entity_type:
            print(f"[Warning] Unknown category: {category}")
            continue
        
        # Call the entity lookup
        entity_id = find_entity_id(example_name, entity_type)
        if entity_id:
            entity_ids[category] = entity_id
        else:
            print(f"[Info] No entity found for {example_name} under {category}")
    
    return entity_ids

def get_recommendations_from_entity_ids(entity_id_map, take=1):
    """
    Given a mapping of category -> entity_id,
    returns recommendations for each category by fetching via Qloo.
    
    Args:
        entity_id_map (dict): {'movies': <entity_id>, 'music': <entity_id>, ...}
        take (int): Number of recommendations to fetch per category
    
    Returns:
        dict: {'movies': [{name, image}, ...], 'music': [...], ...}
    """
    recommendations = {}

    for category, entity_id in entity_id_map.items():
        # Normalize category to lowercase for consistent mapping
        normalized_category = category.strip().lower()

        # Get the corresponding Qloo entity type
        entity_type = ENTITY_TYPE_MAP.get(normalized_category)
        if not entity_type:
            print(f"[Warning] Unknown category '{category}', skipping.")
            continue

        # Fetch recommendations using the entity_id and type
        recs = fetch_individual_recommendation(entity_id, entity_type, take)
        recommendations[category] = recs

    return recommendations

def generate_descriptions_with_categories(title_category_list):
    """
    Uses Gemini to generate 2-line factual descriptions for each title in the list.
    Returns a list of dicts with 'title', 'category', and 'description'.
    """
    

    prompt = (
        "You are given a list of items, where each item is a dictionary with two fields:\n"
        "- 'title': the name of a movie, book, podcast, music artist, or similar item\n"
        "- 'category': the category it belongs to (e.g., 'movies', 'podcast', 'books', 'music')\n\n"
        "Your task is to return a JSON list of dictionaries, where each item has the following fields:\n"
        "- 'title' (string): the same title from input\n"
        "- 'category' (string): the same category from input\n"
        "- 'description' (string): a short, 2-line factual summary of what the title is about. No tone or emotional commentary.\n\n"
        "⚠️ Strict rules:\n"
        "- Output only valid JSON — no markdown, explanations, or formatting\n"
        "- Do not add extra fields\n"
        "- Ensure valid JSON array of objects is returned\n\n"
        "Example input:\n"
        "[\n"
        "  {\"title\": \"The Matrix\", \"category\": \"movies\"}\n"
        "]\n\n"
        "Example output:\n"
        "[\n"
        "  {\n"
        "    \"title\": \"The Matrix\",\n"
        "    \"category\": \"movies\",\n"
        "    \"description\": \"A hacker discovers a hidden virtual reality controlled by machines and joins a rebellion to free humanity.\"\n"
        "  }\n"
        "]\n\n"
        "Now return the JSON output for the following list:\n"
        f"{json.dumps(title_category_list, indent=2)}"
    )

    try:
        response = model.generate_content(prompt)
        content = response.text.strip()

        # Fix common Gemini mistakes if needed
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()

        return json.loads(content)

    except Exception as e:
        print(f"Gemini error: {e}")
        return [
            {
                "category": item['category'],
                "title": item['title'],
                "description": "Description unavailable."
            }
            for item in title_category_list
        ]
