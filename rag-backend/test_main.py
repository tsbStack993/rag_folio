import os
import unittest
from uuid import UUID, uuid4

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("AUTH_SECRET", "unit-test-signing-secret-long-enough")

import main


class ApiHelpersTest(unittest.TestCase):
    def test_maps_nested_database_columns_to_camel_case(self) -> None:
        self.assertEqual(
            main.snake_to_camel(
                {
                    "vector_collection_name": "collection",
                    "rag_metadata": {"token_count": 12},
                }
            ),
            {
                "vectorCollectionName": "collection",
                "ragMetadata": {"tokenCount": 12},
            },
        )

    def test_password_hash_verifies_only_the_original_password(self) -> None:
        encoded = main.hash_password("a strong password")
        self.assertTrue(main.verify_password("a strong password", encoded))
        self.assertFalse(main.verify_password("a different password", encoded))

    def test_signed_token_round_trips_and_rejects_tampering(self) -> None:
        user_id = uuid4()
        token = main.encode_token(user_id)
        self.assertEqual(main.decode_token(token), user_id)
        with self.assertRaises(main.HTTPException):
            main.decode_token(token + "tampered")

    def test_session_request_accepts_frontend_camel_case_id(self) -> None:
        subject_id = uuid4()
        request = main.CreateSession.model_validate({"subjectId": str(subject_id)})
        self.assertEqual(request.subject_id, UUID(str(subject_id)))

    def test_api_exposes_requested_resource_endpoints(self) -> None:
        spec = main.app.openapi()
        paths = set(spec["paths"])
        self.assertTrue(
            {
                "/api/v1/subjects",
                "/api/v1/auth/register",
                "/api/v1/auth/login",
                "/api/v1/auth/me",
                "/api/v1/chat-sessions",
                "/api/v1/chat-sessions/{session_id}/messages",
            }.issubset(paths)
        )
        self.assertIn("HTTPBearer", spec["components"]["securitySchemes"])


if __name__ == "__main__":
    unittest.main()
