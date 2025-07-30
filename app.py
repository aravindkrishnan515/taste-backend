import json
import os
import time
from recommendation import get_examples, map_names_to_entity_ids, get_recommendations, get_item_details, get_activity_recommendations_by_mood, get_genre_based_examples, merge_and_map_entity_ids, get_recommendations_for_activities, get_community_example, find_entity_id, fetch_individual_recommendation, get_opposite_community_journey_cards, get_examples_for_user_and_friends, enrich_recommendations_with_details

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

# Enable more detailed logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

ENTITY_TYPE_MAP = {
    "movies": "urn:entity:movie",
    "books": "urn:entity:book",
    "travel": "urn:entity:place",
    "podcast":"urn:entity:podcast",
    "videogame":"urn:entity:videogame",
    "video games":"urn:entity:videogame",
    "tv_show":"urn:entity:tv_show",
    "tv shows":"urn:entity:tv_show",
    "artist":"urn:entity:artist",
    "music":"urn:entity:album"
}

@app.route('/save-preferences', methods=['POST'])
def save_preferences():
    data = request.get_json()
    preferences = data.get('preferences')
    active_category = data.get('activeCategory', 'movies')  # Default to movies if not provided
    
    print(f"\n==== Received preferences with active category: {active_category} ====\n")
    
    examples = get_examples(preferences)
    
    entity_json = map_names_to_entity_ids(examples)

    # Use the active category for recommendations
    recommendations = get_recommendations(active_category, entity_json)

    print(f"Initial seed recommendations: {examples}")
    print(f"Entity IDs mapped: {entity_json}")
    print(f"Final recommendations for {active_category}: {recommendations.get(active_category, [])}")
    

    if recommendations:
        return jsonify({
            "status": "success",
            "recommendations": recommendations,
        }), 200
    else:
        return jsonify({"status": "error", "message": "Failed to generate recommendations", "preferences": preferences}), 500

@app.route('/get-item-details', methods=['POST'])
def get_item_details_endpoint():
    data = request.get_json()
    category = data.get('category')
    name = data.get('name')
    
    print(f"\n==== Getting details for {name} in category {category} ====\n")
    
    if not category or not name:
        return jsonify({"status": "error", "message": "Category and name are required"}), 400
    
    details = get_item_details(category, name)
    
    print(f"Details: {details}")
    
    return jsonify({"status": "success", "details": details}), 200

@app.route('/daily-recommendations', methods=['POST'])
def daily_recommendations():
    data = request.get_json()
    mood = data.get('mood')
    preferences = data.get('preferences', [])

    print(f"\n==== Getting daily recommendations for mood: {mood} ====\n")

    if not mood:
        return jsonify({"status": "error", "message": "Mood is required"}), 400

    recommendations = get_activity_recommendations_by_mood(mood)

    print(f"Recommendations: {recommendations}")
    
    # Only try to get preference examples if recommendations is a valid dictionary
    preference_example = {}
    if isinstance(recommendations, dict) and not recommendations.get('error'):
        activity_list = list(recommendations.keys())
        print(f"Activity list: {activity_list}")
        
        filtered_preferences = {k: v for k, v in preferences.items() if k in activity_list and v}
        print("filtetred preferences is ", filtered_preferences)

        preference_example = get_genre_based_examples(filtered_preferences)
        print(f"Preference examples: {preference_example}")

    entity_id_result = merge_and_map_entity_ids(recommendations, preference_example)

    entity_id_json = json.dumps(entity_id_result, indent=2)
    print(entity_id_json)

    recommendations = get_recommendations_for_activities(entity_id_result, activity_list)
    print(recommendations)
    return jsonify({
        "status": "success",
        "recommendations": recommendations,
    }), 200


@app.route('/community-recommendations', methods=['POST'])
def community_recommendations():
    data = request.get_json()
    category = data.get('category', 'movies')
    archetype = data.get('archetype', 'Taste Explorer')
    
    print(f"\n==== Community recommendations for {archetype} in {category} category ====\n")
    
    try:
        example = get_community_example(archetype, category)
        category = category.lower()
        entity_type = ENTITY_TYPE_MAP.get(category)
        entity_id = find_entity_id(example, entity_type)
        recommendations = fetch_individual_recommendation(entity_id, entity_type, take=5)
        print(f"API recommendations: {recommendations}")
    except Exception as e:
        print(f"Can't retrive community recommendations: {e}")
        recommendations = []
    
    return jsonify({
        "status": "success",
        "category": category,
        "archetype": archetype,
        "recommendations": recommendations
    }), 200

@app.route('/mismatch-walkin-their-shoes-gemini', methods=['POST'])
def mismatch_walkin_their_shoes_gemini():
    data = request.get_json()
    archetype = data.get('archetype', 'Taste Explorer')
    
    print(f"\n==== Walk in their shoes for {archetype} ====\n")

    # Fetch opposite community journey cards
    try:
        journey_cards = get_opposite_community_journey_cards(archetype)
        print(f"Journey cards: {journey_cards}")
    except Exception as e:
        print(f"Failed to fetch journey cards: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch journey cards"}), 500
    
    return jsonify({
        "status": "success",
        "archetype": archetype,
        "journey_cards": journey_cards
    }), 200

@app.route('/discover-journey-card-recommendations', methods=['POST'])
def discover_journey_card_recommendations():
    data = request.get_json()
    print(data)
    item = data.get('item')
    category = data.get('category')

    try:
        category = category.lower()
        entity_type = ENTITY_TYPE_MAP.get(category)
        entity_id = find_entity_id(item, entity_type)
        recommendations = fetch_individual_recommendation(entity_id, entity_type, take=1)
        print(f"API recommendations: {recommendations}")
    except Exception as e:
        print(f"Can't get recommendations for {item}: {e}")
        recommendations = []

    return jsonify({
        "status": "success",
        "recommendations": recommendations
    }), 200

@app.route('/blend-recommendations', methods=['POST'])
def blend_recommendations():
    data = request.get_json()
    user_preferences = data.get('userPreferences')
    friend_preferences = data.get('friendPreferences')
    print("friend preferences is ", friend_preferences)
    selectedActivities = data.get('selectedActivities')
    preference_example_from_gemini = get_examples_for_user_and_friends(user_preferences, friend_preferences, selectedActivities)
    print(f"Preference examples from Gemini: {preference_example_from_gemini}")

    # Extract examples into lists
    user_preference_example = preference_example_from_gemini.get('user_preference_example')
    friend_preference_examples = preference_example_from_gemini.get('friend_preference_example', [])
    
    print(f"User example: {user_preference_example}")
    print(f"Friend examples: {friend_preference_examples}")
    
    # Find entity IDs
    category = selectedActivities[0]
    entity_type = ENTITY_TYPE_MAP.get(category.lower())
    user_preference_entity_id = find_entity_id(user_preference_example, entity_type)
    print("user preference entity id is", user_preference_entity_id)
    
    all_entity_ids = user_preference_entity_id
    for friend_example in friend_preference_examples:
        friend_entity_id = find_entity_id(friend_example, entity_type)
        if friend_entity_id:
            all_entity_ids += "," + friend_entity_id
     
    print(f"All entity IDs combined: {all_entity_ids}")

    # Fetch recommendations
    try:
        print(f"Calling API with entity_type: {entity_type}")
        recommendations = fetch_individual_recommendation(all_entity_ids, entity_type, take=3)
        print(f"API recommendations: {recommendations}")

        enriched_recommendations = enrich_recommendations_with_details(recommendations, selectedActivities[0])
        print(f"Enriched recommendations: {enriched_recommendations}")
    except Exception as e:
        print(f"Can't get blend recommendations: {e}")
        enriched_recommendations = []
    



    return jsonify({
        "status": "success",
        "recommendations": enriched_recommendations,
        "activity": selectedActivities[0],
        "all_entity_ids": all_entity_ids
    }), 200
    

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Use Render-provided port if available
    app.run(host='0.0.0.0', port=port, debug=True)
