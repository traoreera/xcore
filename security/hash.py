from passlib.context import CryptContext

from . import cfg  # ton module de config


def _get_schemes():
    """Récupère la liste des algorithmes depuis la config."""
    try:
        # Appel à ta config custom
        schemes = cfg.custom_config["password"]["scheme"]
    except Exception:
        # Si la clé n'existe pas, valeur par défaut
        schemes = ["bcrypt"]

    # Transforme en liste propre
    if isinstance(schemes, str):
        schemes = [algo.strip() for algo in schemes.split(",") if algo.strip()]
    return schemes


pwd_cxt = CryptContext(schemes=_get_schemes())


class Hash:
    """Gestion sécurisée du hachage et vérification de mot de passe."""

    @staticmethod
    def hash(password: str) -> str:
        if not password:
            raise ValueError("Le mot de passe ne peut pas être vide.")
        return pwd_cxt.hash(password)

    @staticmethod
    def verify(hashed_password: str, plain_password: str) -> bool:
        if not hashed_password or not plain_password:
            return False

        if not pwd_cxt.verify(
            plain_password,
            hashed_password,
        ):
            return False

        if pwd_cxt.needs_update(hashed_password):
            pass  # TODO: mettre à jour le hachage

        return True
