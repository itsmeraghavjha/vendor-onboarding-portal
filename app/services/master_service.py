from app.extensions import db
from app.models import MasterData

class MasterService:
    # Mapping slugs to DB categories
    SLUG_TO_DB = {
        'region': 'REGION', 'payment-terms': 'PAYMENT_TERM', 'inco-terms': 'INCOTERM',
        'msme-type': 'MSME_TYPE', 'account-group': 'ACCOUNT_GROUP', 'gl-list': 'GL_ACCOUNT',
        'house-bank': 'HOUSE_BANK', 'purch-org': 'PURCHASE_ORG', 'tds-types': 'TAX_TYPE',
        'tds-codes': 'TDS_CODE', 'exemption-reason': 'EXEMPTION_REASON'
    }

    @classmethod
    def save_master(cls, data):
        cat_slug = data.get('category_code', '').lower().replace('_', '-') 
        db_cat = cls.SLUG_TO_DB.get(cat_slug) or data.get('category_code')

        if data.get('id'):
            # Edit
            m = db.session.get(MasterData, data['id'])
            if m: 
                m.code = data['code']
                m.label = data['label']
                m.is_active = data.get('is_active', True)
        else:
            # Create
            if not MasterData.query.filter_by(category=db_cat, code=data['code']).first():
                db.session.add(MasterData(category=db_cat, code=data['code'], label=data['label']))
        db.session.commit()

    @staticmethod
    def toggle_master(master_id):
        m = db.session.get(MasterData, master_id)
        if m: 
            m.is_active = not m.is_active
            db.session.commit()

    @staticmethod
    def delete_master(master_id):
        m = db.session.get(MasterData, master_id)
        if m:
            db.session.delete(m)
            db.session.commit()

    @classmethod
    def get_by_slug(cls, slug):
        db_cat = cls.SLUG_TO_DB.get(slug)
        if not db_cat: return []
        return MasterData.query.filter_by(category=db_cat).order_by(MasterData.code).all()