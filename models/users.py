from config.database import db
from sqlalchemy.sql import func


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(40), primary_key=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    fullname = db.Column(db.String(80), index=True)
    password = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now(), server_default=func.now())