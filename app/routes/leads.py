from flask import Blueprint, request, jsonify, current_app
from app.extensions import mongo
from app.models.lead import Lead
from marshmallow import Schema, fields, ValidationError

leads_bp = Blueprint('leads', __name__, url_prefix='/api/leads')

# Request schema for validation
class LeadSubmissionSchema(Schema):
    name = fields.Str(required=True)
    email = fields.Email(required=True)
    phone = fields.Str(required=True)
    center_name = fields.Str(required=True)
    city = fields.Str(required=True)
    notes = fields.Str(required=False)

@leads_bp.route('/submit', methods=['POST'])
def submit_lead():
    """Submit a new lead from contact form"""
    try:
        # Validate request data
        if not request.json:
            return jsonify({'error': 'Request body is required'}), 400
        
        schema = LeadSubmissionSchema()
        data = schema.load(request.json)
        
        # Additional validation using Lead model validators
        is_valid_name, name_msg = Lead.validate_name(data['name'])
        if not is_valid_name:
            return jsonify({'error': name_msg}), 400
        
        is_valid_email, email_msg = Lead.validate_email(data['email'])
        if not is_valid_email:
            return jsonify({'error': email_msg}), 400
        
        is_valid_phone, phone_msg = Lead.validate_phone(data['phone'])
        if not is_valid_phone:
            return jsonify({'error': phone_msg}), 400
        
        is_valid_center, center_msg = Lead.validate_center_name(data['center_name'])
        if not is_valid_center:
            return jsonify({'error': center_msg}), 400
        
        is_valid_city, city_msg = Lead.validate_city(data['city'])
        if not is_valid_city:
            return jsonify({'error': city_msg}), 400
        
        # Create lead object
        lead = Lead(
            name=data['name'].strip(),
            email=data['email'].strip().lower(),
            phone=data['phone'],
            center_name=data['center_name'].strip(),
            city=data['city'].strip(),
            notes=data.get('notes', '').strip()
        )
        
        # Save to database
        lead_dict = lead.to_dict()
        result = mongo.db.leads.insert_one(lead_dict)
        
        if result.inserted_id:
            # Log successful submission
            print(f"New lead submitted: {lead.name} - {lead.email}")
            
            return jsonify({
                'success': True,
                'message': 'Thank you for your interest! We will get back to you shortly.',
                'lead_id': str(result.inserted_id)
            }), 201
        else:
            return jsonify({'error': 'Failed to save lead'}), 500
    
    except ValidationError as e:
        print(f"Lead submission validation error: {e.messages}")
        return jsonify({'error': 'Validation error', 'details': e.messages}), 400
    except Exception as e:
        print(f"Lead submission error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@leads_bp.route('/list', methods=['GET'])
def list_leads():
    """Get all leads (admin only - can be secured later)"""
    try:
        # Get query parameters for filtering
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))
        
        # Build query
        query = {}
        if status:
            query['status'] = status
        
        # Get leads from database
        leads_cursor = mongo.db.leads.find(query).sort('created_at', -1).skip(skip).limit(limit)
        total_count = mongo.db.leads.count_documents(query)
        
        leads = []
        for lead_data in leads_cursor:
            lead = Lead.from_dict(lead_data)
            leads.append(lead.to_dict())
        
        return jsonify({
            'leads': leads,
            'total': total_count,
            'limit': limit,
            'skip': skip
        }), 200
    
    except Exception as e:
        print(f"Error fetching leads: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@leads_bp.route('/<lead_id>', methods=['GET'])
def get_lead(lead_id):
    """Get a specific lead by ID"""
    try:
        from bson import ObjectId
        
        lead_data = mongo.db.leads.find_one({'_id': ObjectId(lead_id)})
        
        if not lead_data:
            return jsonify({'error': 'Lead not found'}), 404
        
        lead = Lead.from_dict(lead_data)
        return jsonify({'lead': lead.to_dict()}), 200
    
    except Exception as e:
        print(f"Error fetching lead: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@leads_bp.route('/<lead_id>/status', methods=['PUT'])
def update_lead_status(lead_id):
    """Update lead status (admin only - can be secured later)"""
    try:
        from bson import ObjectId
        
        if not request.json or 'status' not in request.json:
            return jsonify({'error': 'Status is required'}), 400
        
        new_status = request.json['status']
        valid_statuses = ['new', 'contacted', 'converted', 'closed']
        
        if new_status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        
        # Get lead from database
        lead_data = mongo.db.leads.find_one({'_id': ObjectId(lead_id)})
        
        if not lead_data:
            return jsonify({'error': 'Lead not found'}), 404
        
        # Update lead
        lead = Lead.from_dict(lead_data)
        lead.update_status(new_status)
        
        # Save to database
        mongo.db.leads.update_one(
            {'_id': ObjectId(lead_id)},
            {'$set': lead.to_dict()}
        )
        
        return jsonify({
            'success': True,
            'message': 'Lead status updated successfully',
            'lead': lead.to_dict()
        }), 200
    
    except Exception as e:
        print(f"Error updating lead status: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

