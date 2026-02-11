from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.db import get_db
from otpprovider import models as otp_models
from otpprovider import utils as otp_utils

from . import Hash
from . import models as auth_models


def init_root():
    try:
        # Vérifier si un admin root existe déjà
        db = next(get_db())
        existing_admin = (
            db.query(auth_models.User)
            .filter(auth_models.User.email == "root@system.local")
            .first()
        )
        if existing_admin:
            print("✅ L'utilisateur root existe déjà.")
            return

        # Créer le rôle root si inexistant
        root_role = (
            db.query(auth_models.Role).filter(auth_models.Role.name == "root").first()
        )
        if not root_role:
            root_role = auth_models.Role(
                name="root",
                description="Super administrateur système avec privilèges complets",
            )
            db.add(root_role)
            db.commit()
            db.refresh(root_role)
            print("🔧 Rôle root créé.")

        # Création du compte root
        hashed_pw = Hash.hash("Root@123")
        root_user = auth_models.User(
            email="root@system.local",
            password_hash=hashed_pw,
            is_active=True,
        )
        db.add(root_user)
        db.commit()
        db.refresh(root_user)
        print("👑 Utilisateur root créé.")

        # Associer le rôle root
        root_user.roles.append(root_role)
        db.commit()

        # Générer et associer le device OTP
        secret = otp_utils.generate_secret()
        otp_device = otp_models.OTPDevice(
            user_id=root_user.id,
            secret=secret,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(otp_device)
        db.commit()

        # Générer le lien QR (Google Authenticator)
        otp_uri = otp_utils.generate_qr_uri(
            secret, root_user.email, issuer="FastAPI Admin Root"
        )

        print("\n🎯 Configuration terminée avec succès.")
        print("----------------------------------------------------")
        print(f"Email Root: {root_user.email}")
        print(f"Mot de passe initial: {password}")
        print(f"Secret OTP: {secret}")
        print(f"URI à scanner (Google Authenticator):\n{otp_uri}")
        print("----------------------------------------------------")
        print("⚠️ Changez le mot de passe immédiatement après connexion.")
        print("⚠️ Scannez le QR dans Google Authenticator pour activer la 2FA.")
        print("----------------------------------------------------")

    except IntegrityError as e:
        print("Erreur d’intégrité :", e)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_root()
