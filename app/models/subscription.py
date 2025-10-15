from datetime import datetime
from bson import ObjectId
from app.extensions import mongo

class Subscription:
    def __init__(self, name, price, description=None, organization_id=None, cycle_type=None):
        self.name = name
        self.price = price
        self.description = description
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.is_active = True
        self.cycle_type = cycle_type
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        return {
            'name': self.name,
            'price': self.price,
            'description': self.description,
            'organization_id': self.organization_id,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'cycle_type': self.cycle_type
        }

    @staticmethod
    def create(name, price, description=None, organization_id=None, cycle_type=None):
        subscription = Subscription(name, price, description, organization_id, cycle_type)
        result = mongo.db.subscriptions.insert_one(subscription.to_dict())
        subscription_dict = subscription.to_dict()
        subscription_dict['_id'] = result.inserted_id
        return subscription_dict

    @staticmethod
    def get_all(organization_id):
        query = {'organization_id': ObjectId(organization_id)} if organization_id else {}
        return list(mongo.db.subscriptions.find(query).sort('created_at', -1))

    @staticmethod
    def get_by_id(subscription_id):
        if not isinstance(subscription_id, ObjectId):
            subscription_id = ObjectId(subscription_id)
        return mongo.db.subscriptions.find_one({'_id': subscription_id})

    @staticmethod
    def update(subscription_id, update_data):
        if not isinstance(subscription_id, ObjectId):
            subscription_id = ObjectId(subscription_id)
        
        update_data['updated_at'] = datetime.utcnow()
        result = mongo.db.subscriptions.update_one(
            {'_id': subscription_id},
            {'$set': update_data}
        )
        return result.modified_count > 0

    @staticmethod
    def toggle_status(subscription_id, active_status, cycle_type):
        if not isinstance(subscription_id, ObjectId):
            subscription_id = ObjectId(subscription_id)
        
        result = mongo.db.subscriptions.update_one(
            {'_id': subscription_id},
            {
                '$set': {
                    'is_active': active_status,
                    'cycle_type': cycle_type,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    @staticmethod
    def delete(subscription_id):
        if not isinstance(subscription_id, ObjectId):
            subscription_id = ObjectId(subscription_id)
        
        result = mongo.db.subscriptions.delete_one({'_id': subscription_id})
        return result.deleted_count > 0
