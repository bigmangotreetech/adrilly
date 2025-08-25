from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import mongo
from app.models.equipment import Equipment
from marshmallow import Schema, fields, ValidationError
from datetime import datetime
from bson import ObjectId

equipment_bp = Blueprint('equipment', __name__, url_prefix='/api/equipment')

# Request schemas
class CreateEquipmentSchema(Schema):
    title = fields.Str(required=True)
    description = fields.Str(required=True)
    price = fields.Float(required=True)
    category = fields.Str(required=False)
    condition = fields.Str(required=False)
    images = fields.List(fields.Str(), required=False)
    contact_info = fields.Dict(required=False)
    location = fields.Str(required=False)
    negotiable = fields.Bool(required=False)

@equipment_bp.route('', methods=['POST'])
@jwt_required()
def create_equipment():
    """Create a new equipment listing"""
    try:
        schema = CreateEquipmentSchema()
        data = schema.load(request.json)
        
        claims = get_jwt()
        user_id = get_jwt_identity()
        organization_id = claims.get('organization_id')
        
        # Create new equipment listing
        new_equipment = Equipment(
            title=data['title'],
            description=data['description'],
            price=data['price'],
            owner_id=user_id,
            organization_id=organization_id,
            category=data.get('category'),
            condition=data.get('condition'),
            images=data.get('images', []),
            contact_info=data.get('contact_info', {})
        )
        
        if 'location' in data:
            new_equipment.location = data['location']
        
        if 'negotiable' in data:
            new_equipment.negotiable = data['negotiable']
        
        result = mongo.db.equipment.insert_one(new_equipment.to_dict())
        new_equipment._id = result.inserted_id
        
        return jsonify({
            'message': 'Equipment listing created successfully',
            'equipment': new_equipment.to_dict()
        }), 201
    
    except ValidationError as e:
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@equipment_bp.route('', methods=['GET'])
def get_equipment():
    """Get equipment listings"""
    try:
        # Build query
        query = {'status': 'available'}
        
        category = request.args.get('category')
        condition = request.args.get('condition')
        search = request.args.get('search')
        
        if category:
            query['category'] = category
        
        if condition:
            query['condition'] = condition
        
        if search:
            query['$or'] = [
                {'title': {'$regex': search, '$options': 'i'}},
                {'description': {'$regex': search, '$options': 'i'}},
                {'tags': {'$in': [search]}}
            ]
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        skip = (page - 1) * per_page
        
        # Execute query
        equipment_cursor = mongo.db.equipment.find(query).sort('created_at', -1).skip(skip).limit(per_page)
        equipment_list = [Equipment.from_dict(equipment_data).to_dict() for equipment_data in equipment_cursor]
        
        # Get total count
        total = mongo.db.equipment.count_documents(query)
        
        return jsonify({
            'equipment': equipment_list,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500 