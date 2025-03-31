from flask import Flask, render_template, jsonify
import mysql.connector
import os
from dotenv import load_dotenv
from flask import request 

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Function to establish DB connection
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password=os.getenv("password"),
            database='vehicle_tracking'
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

@app.route('/')
@app.route('/home')
def index():
    return render_template('index.html')

@app.route('/get_data')
def get_data():
    conn = get_db_connection()
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, plate_number, vehicle_type, confidence, capture_path, detection_time FROM detected_vehicles ORDER BY detection_time DESC"
        cursor.execute(query)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        formatted_data = [
            {
                "id": row["id"],
                "plateNo": row["plate_number"],
                "type": row["vehicle_type"],
                "confidenceScore": round(row["confidence"] * 100, 2),
                "image": row["capture_path"],
                "detectionTime": row["detection_time"].strftime('%d-%m-%y/%I:%M %p')
            }
            for row in data
        ]
        
        return jsonify(formatted_data)
    
    return jsonify({"error": "Database connection failed"}), 500

@app.route('/add_to_whitelist', methods=['POST'])
def add_to_whitelist():
    data = request.json
    owner_name = data.get("name")
    plate_number = data.get("plateNo")
    vehicle_type = data.get("type")

    if not owner_name or not plate_number or not vehicle_type:
        return jsonify({"error": "Missing data"}), 400
    
    # Validate vehicle_type
    valid_types = ["2-wheeler", "3-wheeler", "LMV", "HMV"]
    if vehicle_type not in valid_types:
        return jsonify({"error": "Invalid vehicle type"}), 400

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        query = "INSERT INTO whitelist_vehicles (owner_name, plate_number, vehicle_type) VALUES (%s, %s, %s)"
        cursor.execute(query, (owner_name, plate_number, vehicle_type))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Added to whitelist"}), 201

    return jsonify({"error": "Database connection failed"}), 500

@app.route('/get_whitelist')
def get_whitelist():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, owner_name, plate_number, vehicle_type FROM whitelist_vehicles"
        cursor.execute(query)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        formatted_data = [
            {
                "id": row["id"],
                "name": row["owner_name"],
                "plateNo": row["plate_number"],
                "type": row["vehicle_type"]
            }
            for row in data
        ]
        
        return jsonify(formatted_data)
    
    return jsonify({"error": "Database connection failed"}), 500


if __name__ == '__main__':
    app.run(debug=True)
