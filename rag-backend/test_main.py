import json
import os
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("AUTH_SECRET", "unit-test-signing-secret-long-enough")

import main
import rag_service
import ingest_documents


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

    def test_sse_event_encodes_nested_uuids_and_datetimes(self) -> None:
        message_id = uuid4()
        session_id = uuid4()
        chunk_id = uuid4()
        created_at = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)

        event = main.sse_event(
            {
                "type": "sources",
                "sources": [{"id": chunk_id}],
                "userMessage": {
                    "id": message_id,
                    "session_id": session_id,
                    "created_at": created_at,
                },
            }
        )

        self.assertTrue(event.startswith("data: "))
        payload = json.loads(event.removeprefix("data: ").strip())
        self.assertEqual(payload["sources"][0]["id"], str(chunk_id))
        self.assertEqual(payload["userMessage"]["id"], str(message_id))
        self.assertEqual(payload["userMessage"]["session_id"], str(session_id))
        self.assertEqual(
            payload["userMessage"]["created_at"],
            "2026-09-30T12:00:00+00:00",
        )

    def test_api_exposes_requested_resource_endpoints(self) -> None:
        spec = main.fastapi_app.openapi()
        paths = set(spec["paths"])
        self.assertTrue(
            {
                "/api/v1/subjects",
                "/api/v1/auth/register",
                "/api/v1/auth/login",
                "/api/v1/auth/me",
                "/api/v1/chat-sessions",
                "/api/v1/chat-sessions/{session_id}/messages",
                "/api/v1/chats/{session_id}/stream",
            }.issubset(paths)
        )
        self.assertIn("HTTPBearer", spec["components"]["securitySchemes"])
        self.assertIn(
            "text/event-stream",
            spec["paths"]["/api/v1/chats/{session_id}/stream"]["post"]["responses"]["200"][
                "content"
            ],
        )

    def test_unhandled_errors_return_json_with_frontend_cors_headers(self) -> None:
        @main.fastapi_app.get("/test-unhandled-error")
        def raise_unhandled_error() -> None:
            raise RuntimeError("simulated route failure")

        with patch("main.check_database_connection"):
            with TestClient(main.app, raise_server_exceptions=False) as client:
                response = client.get(
                    "/test-unhandled-error",
                    headers={"Origin": "http://localhost:5173"},
                )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )
        self.assertEqual(response.json()["detail"], "Internal server error")
        self.assertEqual(response.json()["error"], "simulated route failure")

    def test_stream_auth_errors_and_preflight_include_cors_headers(self) -> None:
        with patch("main.check_database_connection"):
            with TestClient(main.app, raise_server_exceptions=False) as client:
                preflight = client.options(
                    f"/api/v1/chats/{uuid4()}/stream",
                    headers={
                        "Origin": "http://localhost:5173",
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "authorization,content-type",
                    },
                )
                unauthorized = client.post(
                    f"/api/v1/chats/{uuid4()}/stream",
                    headers={
                        "Origin": "http://localhost:5173",
                        "Authorization": "Bearer invalid-token",
                    },
                    json={"content": "test"},
                )

        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(
            preflight.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(
            unauthorized.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )
        self.assertEqual(unauthorized.json()["detail"], "Invalid or expired access token")

    def test_lan_login_preflight_allows_credentials_methods_and_headers(self) -> None:
        with patch("main.check_database_connection"):
            with TestClient(main.app, raise_server_exceptions=False) as client:
                response = client.options(
                    "/api/v1/auth/login",
                    headers={
                        "Origin": "http://192.168.1.42:5173",
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "accept,authorization,content-type",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://192.168.1.42:5173",
        )
        self.assertEqual(response.headers["access-control-allow-credentials"], "true")
        self.assertIn("POST", response.headers["access-control-allow-methods"])
        allowed_headers = response.headers["access-control-allow-headers"].lower()
        self.assertIn("accept", allowed_headers)
        self.assertIn("authorization", allowed_headers)
        self.assertIn("content-type", allowed_headers)

    def test_database_connections_use_neon_ssl_and_short_timeout(self) -> None:
        with patch("main.psycopg.connect") as connect:
            with main.database():
                pass
        connect.assert_called_once_with(
            main.DATABASE_URL,
            row_factory=main.dict_row,
            connect_timeout=5,
            sslmode="require",
        )

    def test_lifespan_reports_successful_database_check(self) -> None:
        output = StringIO()
        with patch("main.check_database_connection") as check_database:
            with redirect_stdout(output):
                with TestClient(main.app):
                    pass
        check_database.assert_called_once_with()
        self.assertIn("[SUCCESS] Connected to Neon DB", output.getvalue())

    def test_vector_literal_requires_768_finite_values(self) -> None:
        self.assertTrue(rag_service.vector_literal([0.0] * 768).startswith("[0.0,"))
        with self.assertRaises(ValueError):
            rag_service.vector_literal([0.0])
        with self.assertRaises(ValueError):
            rag_service.vector_literal([float("nan")] * 768)

    def test_rag_prompt_includes_history_and_retrieved_content(self) -> None:
        messages = rag_service.build_messages(
            "What does it explain?",
            [{"title": "Lecture", "page": 4, "content": "Relevant fact."}],
            [{"role": "user", "content": "Earlier question."}],
        )
        self.assertIn("Relevant fact.", messages[0]["content"])
        self.assertEqual(messages[1]["content"], "Earlier question.")
        self.assertEqual(messages[2]["content"], "What does it explain?")

    def test_starter_documents_cover_all_subjects_and_chunk_into_target_size(self) -> None:
        self.assertEqual(
            set(ingest_documents.STARTER_DOCUMENTS),
            {
                "embedded-system",
                "cloud-technology",
                "digital-image-processing",
                "digital-signal-processing",
                "software-engineering",
            },
        )
        for _, text in ingest_documents.STARTER_DOCUMENTS.values():
            chunks = ingest_documents.chunk_text(text)
            self.assertTrue(chunks)
            self.assertTrue(
                all(
                    ingest_documents.CHUNK_MIN_WORDS
                    <= len(chunk.split())
                    <= ingest_documents.CHUNK_MAX_WORDS
                    for chunk in chunks
                )
            )

    def test_long_starter_text_chunks_overlap_and_stay_within_bounds(self) -> None:
        words = [f"word{index}." for index in range(1100)]
        chunks = ingest_documents.chunk_text(" ".join(words))
        self.assertTrue(
            all(
                ingest_documents.CHUNK_MIN_WORDS
                <= len(chunk.split())
                <= ingest_documents.CHUNK_MAX_WORDS
                for chunk in chunks
            )
        )
        self.assertEqual(
            chunks[0].split()[-ingest_documents.CHUNK_OVERLAP_WORDS :],
            chunks[1].split()[: ingest_documents.CHUNK_OVERLAP_WORDS],
        )


if __name__ == "__main__":
    unittest.main()
