#!/usr/bin/env python3
"""
BDL Gate Management System Backend - Enhanced Version
A Python backend using SQLite for the BDL Gate Management System
With QR codes, photo capture, and pre-registration features
"""

import sqlite3
import json
import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import hashlib
import qrcode
import base64

app = Flask(__name__)
CORS(app)

# Database setup
DB_PATH = 'bdl_gatepass.db'

# Static files directory
STATIC_DIR = 'static'
QR_VISITORS_DIR = os.path.join(STATIC_DIR, 'qr_visitors')
QR_VEHICLES_DIR = os.path.join(STATIC_DIR, 'qr_vehicles')

# Create directories
os.makedirs(QR_VISITORS_DIR, exist_ok=True)
os.makedirs(QR_VEHICLES_DIR, exist_ok=True)

def init_database():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'guard',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create visitors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            destination TEXT NOT NULL,
            purpose TEXT NOT NULL,
            checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            checkout_time TIMESTAMP NULL,
            status TEXT DEFAULT 'IN',
            photo_path TEXT NULL
        )
    ''')
    
    # Create vehicles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_name TEXT NOT NULL,
            plate_number TEXT UNIQUE NOT NULL,
            mileage_in INTEGER NOT NULL,
            checkin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mileage_out INTEGER NULL,
            checkout_time TIMESTAMP NULL,
            status TEXT DEFAULT 'IN',
            photo_path TEXT NULL
        )
    ''')
    
    # Insert default admin user if not exists
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, role)
        VALUES (?, ?, ?)
    ''', ('admin', hash_password('admin123'), 'admin'))
    
    # Insert default guard user if not exists
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, role)
        VALUES (?, ?, ?)
    ''', ('guard1', hash_password('gate1'), 'guard'))
    
    conn.commit()
    conn.close()

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hash_value):
    """Verify password against hash"""
    return hash_password(password) == hash_value

@app.route('/api/login', methods=['POST'])
def login():
    """User login endpoint"""
    data = request.get_json()
    username = data.get('username', '').lower().strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT username, password_hash, role FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and verify_password(password, user[1]):
        return jsonify({
            'success': True,
            'username': user[0],
            'role': user[2]
        })
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/api/visitors', methods=['GET'])
def get_visitors():
    """Get all visitors"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, destination, purpose, checkin_time, checkout_time, status, photo_path
        FROM visitors ORDER BY checkin_time DESC
    ''')
    visitors = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        'id': v[0],
        'name': v[1],
        'destination': v[2],
        'purpose': v[3],
        'checkin_time': v[4],
        'checkout_time': v[5],
        'status': v[6],
        'photo_path': v[7]
    } for v in visitors])

@app.route('/api/visitors', methods=['POST'])
def manage_visitor():
    """Manage visitor check-in/check-out"""
    data = request.get_json()
    action = data.get('action')
    
    if action == 'checkin':
        name = data.get('name', '').strip()
        destination = data.get('destination', '').strip()
        purpose = data.get('purpose', '').strip()
        
        if not all([name, destination, purpose]):
            return jsonify({'success': False, 'message': 'All fields required for check-in'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO visitors (name, destination, purpose)
            VALUES (?, ?, ?)
        ''', (name, destination, purpose))
        conn.commit()
        
        # Get the visitor ID
        visitor_id = cursor.lastrowid
        
        # Generate QR code
        qr_data = f"VISITOR:{visitor_id}:{name}:{destination}:{purpose}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        qr_path = os.path.join(QR_VISITORS_DIR, f"visitor_{visitor_id}.png")
        img.save(qr_path)
        
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Visitor checked in successfully',
            'visitor_id': visitor_id,
            'qr_code': f"/static/qr_visitors/visitor_{visitor_id}.png"
        })
    
    elif action == 'checkout':
        identifier = data.get('identifier', '').strip()
        
        if not identifier:
            return jsonify({'success': False, 'message': 'Visitor name required for check-out'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Find visitor by name (case insensitive)
        cursor.execute('''
            SELECT id, status FROM visitors 
            WHERE LOWER(name) = LOWER(?) AND status = 'IN'
            ORDER BY checkin_time DESC LIMIT 1
        ''', (identifier,))
        visitor = cursor.fetchone()
        
        if not visitor:
            conn.close()
            return jsonify({'success': False, 'message': 'Visitor not found or already checked out'}), 404
        
        cursor.execute('''
            UPDATE visitors 
            SET checkout_time = CURRENT_TIMESTAMP, status = 'OUT'
            WHERE id = ?
        ''', (visitor[0],))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Visitor checked out successfully'})
    
    else:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400

@app.route('/api/vehicles', methods=['GET'])
def get_vehicles():
    """Get all vehicles"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, driver_name, plate_number, mileage_in, checkin_time, mileage_out, checkout_time, status, photo_path
        FROM vehicles ORDER BY checkin_time DESC
    ''')
    vehicles = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        'id': v[0],
        'driver_name': v[1],
        'plate_number': v[2],
        'mileage_in': v[3],
        'checkin_time': v[4],
        'mileage_out': v[5],
        'checkout_time': v[6],
        'status': v[7],
        'photo_path': v[8]
    } for v in vehicles])

@app.route('/api/vehicles', methods=['POST'])
def manage_vehicle():
    """Manage vehicle check-in/check-out"""
    data = request.get_json()
    action = data.get('action')
    
    if action == 'checkin':
        driver_name = data.get('driver', '').strip()
        plate_number = data.get('plate', '').strip().upper()
        mileage_in = data.get('m_in')
        
        if not all([driver_name, plate_number, mileage_in]):
            return jsonify({'success': False, 'message': 'All fields required for check-in'}), 400
        
        try:
            mileage_in = int(mileage_in)
        except ValueError:
            return jsonify({'success': False, 'message': 'Mileage must be a number'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if vehicle is already in
        cursor.execute('SELECT id FROM vehicles WHERE plate_number = ? AND status = "IN"', (plate_number,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return jsonify({'success': False, 'message': 'Vehicle already checked in'}), 400
        
        try:
            cursor.execute('''
                INSERT INTO vehicles (driver_name, plate_number, mileage_in)
                VALUES (?, ?, ?)
            ''', (driver_name, plate_number, mileage_in))
            conn.commit()
            
            # Get the vehicle ID
            vehicle_id = cursor.lastrowid
            
            # Generate QR code
            qr_data = f"VEHICLE:{vehicle_id}:{driver_name}:{plate_number}"
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            qr_path = os.path.join(QR_VEHICLES_DIR, f"vehicle_{vehicle_id}.png")
            img.save(qr_path)
            
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'success': False, 'message': 'Vehicle with this plate number already exists'}), 409
        finally:
            conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Vehicle checked in successfully',
            'vehicle_id': vehicle_id,
            'qr_code': f"/static/qr_vehicles/vehicle_{vehicle_id}.png"
        })
    
    elif action == 'checkout':
        plate_number = data.get('identifier', '').strip().upper()
        mileage_out = data.get('m_out')
        
        if not plate_number:
            return jsonify({'success': False, 'message': 'Plate number required for check-out'}), 400
        
        try:
            if mileage_out:
                mileage_out = int(mileage_out)
        except ValueError:
            return jsonify({'success': False, 'message': 'Mileage must be a number'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Find vehicle by plate number
        cursor.execute('''
            SELECT id, mileage_in FROM vehicles 
            WHERE plate_number = ? AND status = 'IN'
            ORDER BY checkin_time DESC LIMIT 1
        ''', (plate_number,))
        vehicle = cursor.fetchone()
        
        if not vehicle:
            conn.close()
            return jsonify({'success': False, 'message': 'Vehicle not found or already checked out'}), 404
        
        # Update vehicle record
        cursor.execute('''
            UPDATE vehicles 
            SET mileage_out = ?, checkout_time = CURRENT_TIMESTAMP, status = 'OUT'
            WHERE id = ?
        ''', (mileage_out, vehicle[0]))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Vehicle checked out successfully'})
    
    else:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users (admin only)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, role, created_at FROM users ORDER BY role, username')
    users = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        'id': u[0],
        'username': u[1],
        'role': u[2],
        'created_at': u[3]
    } for u in users])

@app.route('/api/users', methods=['POST'])
def manage_users():
    """Add new user (admin only)"""
    data = request.get_json()
    username = data.get('username', '').lower().strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'guard')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        ''', (username, hash_password(password), role))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'User created successfully'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'message': 'Username already exists'}), 409

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete user (admin only)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Don't allow deletion of admin user
    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    if user[0] == 'admin':
        conn.close()
        return jsonify({'success': False, 'message': 'Cannot delete admin user'}), 400
    
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'User deleted successfully'})

@app.route('/api/admin/password', methods=['POST'])
def update_admin_password():
    """Update admin password"""
    data = request.get_json()
    new_password = data.get('password', '').strip()
    
    if not new_password:
        return jsonify({'success': False, 'message': 'Password required'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET password_hash = ? WHERE username = 'admin'
    ''', (hash_password(new_password),))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Admin password updated successfully'})

@app.route('/api/search/<entity>', methods=['GET'])
def search_entity(entity):
    """Search visitors or vehicles by name/plate"""
    query = request.args.get('q', '').lower().strip()
    
    if not query:
        return jsonify({'success': False, 'message': 'Search query required'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if entity == 'visitors':
        cursor.execute('''
            SELECT id, name, destination, purpose, checkin_time, checkout_time, status, photo_path
            FROM visitors WHERE LOWER(name) LIKE ? ORDER BY checkin_time DESC
        ''', (f'%{query}%',))
        results = cursor.fetchall()
        columns = ['id', 'name', 'destination', 'purpose', 'checkin_time', 'checkout_time', 'status', 'photo_path']
    elif entity == 'vehicles':
        cursor.execute('''
            SELECT id, driver_name, plate_number, mileage_in, checkin_time, mileage_out, checkout_time, status, photo_path
            FROM vehicles WHERE LOWER(plate_number) LIKE ? ORDER BY checkin_time DESC
        ''', (f'%{query}%',))
        results = cursor.fetchall()
        columns = ['id', 'driver_name', 'plate_number', 'mileage_in', 'checkin_time', 'mileage_out', 'checkout_time', 'status', 'photo_path']
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid entity type'}), 400
    
    conn.close()
    
    return jsonify([dict(zip(columns, row)) for row in results])

@app.route('/api/qr/scan', methods=['POST'])
def scan_qr():
    """Scan QR code for quick check-out"""
    data = request.get_json()
    qr_data = data.get('qr_data', '').strip()
    
    if not qr_data:
        return jsonify({'success': False, 'message': 'QR data required'}), 400
    
    # Parse QR data
    if qr_data.startswith("VISITOR:"):
        parts = qr_data.split(":")
        if len(parts) >= 5:
            visitor_id = int(parts[1])
            return handle_qr_visitor_checkout(visitor_id)
    
    elif qr_data.startswith("VEHICLE:"):
        parts = qr_data.split(":")
        if len(parts) >= 4:
            vehicle_id = int(parts[1])
            return handle_qr_vehicle_checkout(vehicle_id)
    
    return jsonify({'success': False, 'message': 'Invalid QR code'}), 400

def handle_qr_visitor_checkout(visitor_id):
    """Handle visitor check-out via QR code"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Find visitor by ID
    cursor.execute('''
        SELECT id, status FROM visitors 
        WHERE id = ? AND status = 'IN'
    ''', (visitor_id,))
    visitor = cursor.fetchone()
    
    if not visitor:
        conn.close()
        return jsonify({'success': False, 'message': 'Visitor not found or already checked out'}), 404
    
    cursor.execute('''
        UPDATE visitors 
        SET checkout_time = CURRENT_TIMESTAMP, status = 'OUT'
        WHERE id = ?
    ''', (visitor[0],))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Visitor checked out successfully'})

def handle_qr_vehicle_checkout(vehicle_id):
    """Handle vehicle check-out via QR code"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Find vehicle by ID
    cursor.execute('''
        SELECT id, mileage_in FROM vehicles 
        WHERE id = ? AND status = 'IN'
    ''', (vehicle_id,))
    vehicle = cursor.fetchone()
    
    if not vehicle:
        conn.close()
        return jsonify({'success': False, 'message': 'Vehicle not found or already checked out'}), 404
    
    # Update vehicle record (mileage_out is optional for QR check-out)
    cursor.execute('''
        UPDATE vehicles 
        SET checkout_time = CURRENT_TIMESTAMP, status = 'OUT'
        WHERE id = ?
    ''', (vehicle[0],))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Vehicle checked out successfully'})

@app.route('/api/pre-register', methods=['POST'])
def pre_register_visitor():
    """Pre-register a visitor by an employee"""
    data = request.get_json()
    name = data.get('name', '').strip()
    destination = data.get('destination', '').strip()
    purpose = data.get('purpose', '').strip()
    employee_name = data.get('employee_name', '').strip()
    
    if not all([name, destination, purpose, employee_name]):
        return jsonify({'success': False, 'message': 'All fields required for pre-registration'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if already pre-registered today
    cursor.execute('''
        SELECT id FROM visitors 
        WHERE name = ? AND destination = ? AND status = 'PRE-REGISTERED'
        AND DATE(checkin_time) = DATE('now')
    ''', (name, destination))
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        return jsonify({'success': False, 'message': 'Visitor already pre-registered today'}), 409
    
    cursor.execute('''
        INSERT INTO visitors (name, destination, purpose, status)
        VALUES (?, ?, ?, 'PRE-REGISTERED')
    ''', (name, destination, purpose))
    conn.commit()
    
    # Get the visitor ID
    visitor_id = cursor.lastrowid
    
    # Generate QR code for pre-registration
    qr_data = f"PREGISTERED:{visitor_id}:{name}:{destination}:{purpose}:{employee_name}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    qr_path = os.path.join(QR_VISITORS_DIR, f"pre_registered_{visitor_id}.png")
    img.save(qr_path)
    
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': 'Visitor pre-registered successfully',
        'visitor_id': visitor_id,
        'qr_code': f"/static/qr_visitors/pre_registered_{visitor_id}.png"
    })

@app.route('/api/confirm-pre-registration', methods=['POST'])
def confirm_pre_registration():
    """Confirm pre-registered visitor arrival"""
    data = request.get_json()
    qr_data = data.get('qr_data', '').strip()
    
    if not qr_data:
        return jsonify({'success': False, 'message': 'QR data required'}), 400
    
    # Parse pre-registration QR data
    if qr_data.startswith("PREGISTERED:"):
        parts = qr_data.split(":")
        if len(parts) >= 6:
            visitor_id = int(parts[1])
            return handle_pre_registration_confirmation(visitor_id)
    
    return jsonify({'success': False, 'message': 'Invalid pre-registration QR code'}), 400

def handle_pre_registration_confirmation(visitor_id):
    """Handle pre-registration confirmation"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Find pre-registered visitor
    cursor.execute('''
        SELECT id, name, destination, purpose FROM visitors 
        WHERE id = ? AND status = 'PRE-REGISTERED'
    ''', (visitor_id,))
    visitor = cursor.fetchone()
    
    if not visitor:
        conn.close()
        return jsonify({'success': False, 'message': 'Pre-registered visitor not found'}), 404
    
    # Update to checked in
    cursor.execute('''
        UPDATE visitors 
        SET checkin_time = CURRENT_TIMESTAMP, status = 'IN'
        WHERE id = ?
    ''', (visitor[0],))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Visitor confirmed and checked in successfully'})

@app.route('/api/photos', methods=['POST'])
def upload_photo():
    """Upload photo from browser camera"""
    data = request.get_json()
    photo_data = data.get('photo', '').strip()
    entity_type = data.get('type', '').strip()  # 'visitor' or 'vehicle'
    entity_id = data.get('id', None)
    
    if not photo_data or not entity_type or not entity_id:
        return jsonify({'success': False, 'message': 'Photo data, type, and ID required'}), 400
    
    # Decode base64 photo
    try:
        photo_bytes = base64.b64decode(photo_data.split(',')[1])  # Remove data:image/...;base64, prefix
    except:
        return jsonify({'success': False, 'message': 'Invalid photo format'}), 400
    
    # Save photo
    photo_dir = os.path.join(STATIC_DIR, 'photos', entity_type + 's')
    os.makedirs(photo_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    photo_filename = f"{entity_type}_{entity_id}_{timestamp}.jpg"
    photo_path = os.path.join(photo_dir, photo_filename)
    
    with open(photo_path, 'wb') as f:
        f.write(photo_bytes)
    
    # Update database with photo path
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if entity_type == 'visitor':
        cursor.execute('''
            UPDATE visitors SET photo_path = ? WHERE id = ?
        ''', (photo_path, entity_id))
    elif entity_type == 'vehicle':
        cursor.execute('''
            UPDATE vehicles SET photo_path = ? WHERE id = ?
        ''', (photo_path, entity_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': 'Photo uploaded successfully',
        'photo_url': f"/static/photos/{entity_type}s/{photo_filename}"
    })

# Serve static files
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'database': 'connected',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    init_database()
    print("BDL Gate Management System Backend - Enhanced Version")
    print("Database initialized at:", DB_PATH)
    print("Starting server on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)