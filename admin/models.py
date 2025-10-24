from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from database import Base
from dependencies import make_ids

# Table d’association
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(30), ForeignKey("users.id")),
    Column("role_id", String(30), ForeignKey("roles.id")),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(30), ForeignKey("roles.id")),
    Column("permission_id", String(30), ForeignKey("permissions.id")),
)


class Role(Base):
    __tablename__ = "roles"
    id = Column(String(30), primary_key=True, index=True, default=make_ids())
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))

    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )


class Permission(Base):
    __tablename__ = "permissions"
    id = Column(String(30), primary_key=True, default=make_ids(), index=True)
    role_id = Column(String(30), ForeignKey("roles.id"))
    name = Column(String(100), unique=True)
    description = Column(String(255))

    roles = relationship(
        "Role", secondary="role_permissions", back_populates="permissions"
    )
