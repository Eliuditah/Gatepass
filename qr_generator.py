#!/usr/bin/env python3
"""
QR Code Generator for BDL Gate Management System
Generates QR codes for visitors and vehicles for quick check-out
"""

import qrcode
import base64
import os
from datetime import datetime
import sqlite3

def generate_visitor_qr(visitor_id, name, destination, purpose):
    """Generate QR code for visitor check-out"""
    # Create QR data
    qr_data = f"VISITOR:{visitor_id}:{name}:{destination}:{purpose}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code
    qr_path = f"static/qr_visitors/visitor_{visitor_id}.png"
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    img.save(qr_path)
    
    return qr_path

def generate_vehicle_qr(vehicle_id, driver_name, plate_number):
    """Generate QR code for vehicle check-out"""
    # Create QR data
    qr_data = f"VEHICLE:{vehicle_id}:{driver_name}:{plate_number}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code
    qr_path = f"static/qr_vehicles/vehicle_{vehicle_id}.png"
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    img.save(qr_path)
    
    return qr_path

def parse_qr_data(qr_data):
    """Parse QR code data to extract entity information"""
    if qr_data.startswith("VISITOR:"):
        parts = qr_data.split(":")
        return {
            'type': 'visitor',
            'id': int(parts[1]),
            'name': parts[2],
            'destination': parts[3],
            'purpose': parts[4]
        }
    elif qr_data.startswith("VEHICLE:"):
        parts = qr_data.split(":")
        return {
            'type': 'vehicle',
            'id': int(parts[1]),
            'driver_name': parts[2],
            'plate_number': parts[3]
        }
    return None

def get_qr_image_base64(qr_path):
    """Get QR code image as base64 string"""
    if os.path.exists(qr_path):
        with open(qr_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    return None

if __name__ == "__main__":
    # Test QR generation
    print("QR Code Generator for BDL Gate Management System")
    print("This module generates QR codes for quick check-out functionality")