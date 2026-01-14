import jwt
import datetime
import os
from dotenv import load_dotenv

load_dotenv()


class AuthSpecialist:
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET", "cistem_secret_key_2026")
        self.admin_email = os.getenv("ADMIN_EMAIL", "admin@cistemlabs.ai")
        self.admin_password = os.getenv("ADMIN_PASSWORD", "secure_password")

    def generate_token(self, email, password):
        """Valida credenciales y genera un JWT válido por 24 horas"""
        if email == self.admin_email and password == self.admin_password:
            payload = {
                "email": email,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
                "iat": datetime.datetime.utcnow()
            }
            token = jwt.encode(payload, self.secret_key, algorithm="HS256")
            return token
        return None

    def verify_token(self, token):
        """Decodifica y valida la integridad del token"""
        try:
            # Si el token viene con el prefijo 'Bearer ', lo removemos
            if token.startswith("Bearer "):
                token = token.split(" ")[1]

            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None