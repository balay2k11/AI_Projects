from flask import Flask, request, jsonify
from flask_cors import CORS
from deep_translator import GoogleTranslator

app = Flask(__name__)
CORS(app)

@app.route("/translate", methods=["POST"])
def translate_text():
    data = request.get_json()
    text = data.get("text")

    if not text:
        return jsonify({"error": "Text is required"}), 400

    tamil_text = GoogleTranslator(
        source="en",
        target="ta"
    ).translate(text)

    return jsonify({
        "english": text,
        "tamil": tamil_text
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
