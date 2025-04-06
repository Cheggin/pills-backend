from flask import Flask, request, jsonify
import base64
from flask_cors import CORS
from PIL import Image
from io import BytesIO
from inference import (
    query_pill_features, query_drugs, query_side_effects, query_ddi
)

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return 'Pill ID Gemini API is running!'

@app.route('/analyze-both', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        image1_b64 = data.get('image1')
        image2_b64 = data.get('image2')
        if not image1_b64 or not image2_b64:
            return jsonify({'error': 'Both images are required'}), 400

        # Decode images and combine them
        image1_bytes = base64.b64decode(image1_b64)
        image2_bytes = base64.b64decode(image2_b64)
        image1 = Image.open(BytesIO(image1_bytes))
        image2 = Image.open(BytesIO(image2_bytes))
        total_height = image1.height + image2.height
        new_image = Image.new('RGB', (max(image1.width, image2.width), total_height))
        new_image.paste(image1, (0, 0))
        new_image.paste(image2, (0, image1.height))
        combined_image_bytes = BytesIO()
        new_image.save(combined_image_bytes, format='PNG')
        combined_image_bytes.seek(0)
        combined_image_bytes = combined_image_bytes.read()
        
        result = query_drugs(*query_pill_features(combined_image_bytes))
        print(result["1st choice"])
        return jsonify(result)
    except Exception as e:
        print(f'Error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/side-effects', methods=['GET'])
def get_side_effects():
    try:
        drug_name = request.args.get('drug_name')
        if not drug_name:
            return jsonify({'error': 'Drug name is required'}), 400
        side_effects = query_side_effects(drug_name)
        return jsonify({'side_effects': side_effects})
    except Exception as e:
        print(f'Error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/ddi', methods=['GET'])
def get_ddi():
    try:
        drug1_name = request.args.get('drug1_name')
        drug2_name = request.args.get('drug2_name')
        if not drug1_name or not drug2_name:
            return jsonify({'error': 'Both drug names are required'}), 400
        ddi_result = query_ddi(drug1_name, drug2_name)
        return jsonify({'ddi': ddi_result})
    except Exception as e:
        print(f'Error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

# @app.route('/get_all_info', methods=['GET'])
# def get_all_info_api():
#     try:
#         drug_name = request.args.get('drug_name')
#         print(drug_name)
#         limit = request.args.get('limit', default=1, type=int)
#         if not drug_name:
#             return jsonify({'error': 'Drug name is required'}), 400
#         all_info = get_all_info(drug_name, limit)
#         return jsonify({'all_info': all_info})
#     except Exception as e:
#         print(f'Error: {e}')
#         return jsonify({'error': 'Internal server error'}), 500

# @app.route('/get_ask_doctor', methods=['GET'])
# def get_ask_doctor_api():
#     drug_name = request.args.get('drug_name')
#     limit = request.args.get('limit', default=1, type=int)
#     if not drug_name:
#         return jsonify({'error': 'Drug name is required'}), 400
#     data = get_ask_doctor(drug_name, limit)
#     return jsonify({'ask_doctor': data})

# @app.route('/get_ask_doctor_or_pharmacist', methods=['GET'])
# def get_ask_doctor_or_pharmacist_api():
#     drug_name = request.args.get('drug_name')
#     limit = request.args.get('limit', default=1, type=int)
#     if not drug_name:
#         return jsonify({'error': 'Drug name is required'}), 400
#     data = get_ask_doctor_or_pharmacist(drug_name, limit)
#     return jsonify({'ask_doctor_or_pharmacist': data})

# @app.route('/get_stop_use', methods=['GET'])
# def get_stop_use_api():
#     drug_name = request.args.get('drug_name')
#     limit = request.args.get('limit', default=1, type=int)
#     if not drug_name:
#         return jsonify({'error': 'Drug name is required'}), 400
#     data = get_stop_use(drug_name, limit)
#     return jsonify({'stop_use': data})

# @app.route('/get_pregnancy_or_breast_feeding', methods=['GET'])
# def get_pregnancy_or_breast_feeding_api():
#     drug_name = request.args.get('drug_name')
#     limit = request.args.get('limit', default=1, type=int)
#     if not drug_name:
#         return jsonify({'error': 'Drug name is required'}), 400
#     data = get_pregnancy_or_breast_feeding(drug_name, limit)
#     return jsonify({'pregnancy_or_breast_feeding': data})

# @app.route('/get_keep_out_of_reach_of_children', methods=['GET'])
# def get_keep_out_of_reach_of_children_api():
#     drug_name = request.args.get('drug_name')
#     limit = request.args.get('limit', default=1, type=int)
#     if not drug_name:
#         return jsonify({'error': 'Drug name is required'}), 400
#     data = get_keep_out_of_reach_of_children(drug_name, limit)
#     return jsonify({'keep_out_of_reach_of_children': data})

# @app.route('/get_dosage_and_administration', methods=['GET'])
# def get_dosage_and_administration_api():
#     drug_name = request.args.get('drug_name')
#     limit = request.args.get('limit', default=1, type=int)
#     if not drug_name:
#         return jsonify({'error': 'Drug name is required'}), 400
#     data = get_dosage_and_administration(drug_name, limit)
#     return jsonify({'dosage_and_administration': data})

# @app.route('/get_dosage_and_administration_table', methods=['GET'])
# def get_dosage_and_administration_table_api():
#     drug_name = request.args.get('drug_name')
#     limit = request.args.get('limit', default=1, type=int)
#     if not drug_name:
#         return jsonify({'error': 'Drug name is required'}), 400
#     data = get_dosage_and_administration_table(drug_name, limit)
#     return jsonify({'dosage_and_administration_table': data})

# @app.route('/get_storage_and_handling', methods=['GET'])
# def get_storage_and_handling_api():
#     drug_name = request.args.get('drug_name')
#     limit = request.args.get('limit', default=1, type=int)
#     if not drug_name:
#         return jsonify({'error': 'Drug name is required'}), 400
#     data = get_storage_and_handling(drug_name, limit)
#     return jsonify({'storage_and_handling': data})

# @app.route('/get_purpose', methods=['GET'])
# def get_purpose_api():
#     drug_name = request.args.get('drug_name')
#     limit = request.args.get('limit', default=1, type=int)
#     if not drug_name:
#         return jsonify({'error': 'Drug name is required'}), 400
#     data = get_purpose(drug_name, limit)
#     return jsonify({'purpose': data})

# @app.route('/get_indications_and_usage', methods=['GET'])
# def get_indications_and_usage_api():
#     drug_name = request.args.get('drug_name')
#     limit = request.args.get('limit', default=1, type=int)
#     if not drug_name:
#         return jsonify({'error': 'Drug name is required'}), 400
#     data = get_indications_and_usage(drug_name, limit)
#     return jsonify({'indications_and_usage': data})

@app.route('/test', methods=['GET'])
def test():
    return jsonify({'message': 'Test endpoint is working!'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
