from app.extensions import db
from app.models import User

class UserService:
    @staticmethod
    def create_or_update_user(data):
        """
        Creates a new user or updates an existing one.
        Expects data dictionary with: id, name, email, dept, role, category.
        """
        user_id = data.get('id')
        name = data.get('name')
        email = data.get('email')
        dept = data.get('dept')
        role = data.get('role')
        category = data.get('category')

        # Basic Validation
        if not name or not email:
            raise ValueError("User Name and Email are mandatory fields.")

        if user_id:
            # UPDATE EXISTING
            user = db.session.get(User, user_id)
            if not user:
                raise ValueError("User not found.")
            user.username = name
            user.email = email
            user.department = dept
            user.role = role
            user.assigned_category = category
        else:
            # CREATE NEW
            if User.query.filter_by(email=email).first():
                raise ValueError("User with this email already exists.")
            
            new_user = User(username=name, email=email, department=dept, role=role, assigned_category=category)
            new_user.set_password('pass123') # Default password policy
            db.session.add(new_user)
        
        db.session.commit()
        return True

    @staticmethod
    def delete_user(user_id):
        """Deletes a user, protecting admins."""
        user = db.session.get(User, user_id)
        if user:
            if user.role == 'admin':
                raise ValueError("Cannot delete an Administrator.")
            db.session.delete(user)
            db.session.commit()
            return True
        return False