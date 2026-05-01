"""
System Settings Model
"""
from sqlalchemy import Column, Integer, String, Boolean
from app.db.database import Base

class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(String(500), nullable=True)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<SystemSettings {self.key}={self.value}>"
