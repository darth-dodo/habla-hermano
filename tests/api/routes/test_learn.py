"""Tests for learning path routes (GET /learn/).

Covers the main learning path page and the HTMX recommendation partial.
Uses the shared test_client fixture from conftest.py which provides a full
FastAPI app with mocked auth (user=mock_user via OptionalUserDep override).

DB access via _get_user_learning_data is patched to avoid Supabase calls.
The PathService and AdaptiveService use real lesson YAML files from
data/lessons/ so path construction and progress overlays are realistic.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Module path for patching helpers inside the learn route module.
_LEARN_MODULE = "src.api.routes.learn"


# =============================================================================
# GET /learn/ -- Main Learning Path Page
# =============================================================================


class TestLearnPageRoute:
    """Tests for GET /learn/ endpoint."""

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_returns_200(self, mock_data: MagicMock, test_client: TestClient) -> None:
        """GET /learn/ should return 200 OK."""
        response = test_client.get("/learn/")
        assert response.status_code == 200

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_returns_html_content_type(self, mock_data: MagicMock, test_client: TestClient) -> None:
        """GET /learn/ should return text/html content type."""
        response = test_client.get("/learn/")
        assert "text/html" in response.headers["content-type"]

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_contains_learning_path_heading(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Response should contain the Learning Path heading."""
        response = test_client.get("/learn/")
        assert "Learning Path" in response.text

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_default_language_is_spanish(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Default language parameter should be 'es' (Spanish)."""
        response = test_client.get("/learn/")
        assert "Spanish" in response.text

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_language_parameter_switches_path(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Passing language=de should render the German learning path."""
        response = test_client.get("/learn/?language=de")
        assert response.status_code == 200
        assert "German" in response.text

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_french_language_parameter(self, mock_data: MagicMock, test_client: TestClient) -> None:
        """Passing language=fr should render the French learning path."""
        response = test_client.get("/learn/?language=fr")
        assert response.status_code == 200
        assert "French" in response.text

    def test_unsupported_language_falls_back_to_default(self, test_client: TestClient) -> None:
        """Unsupported language code should fall back to default (Spanish)."""
        response = test_client.get("/learn/?language=xx")
        assert response.status_code == 200
        assert "Spanish" in response.text

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_contains_path_timeline_units(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Response should contain the unit titles from the path structure."""
        response = test_client.get("/learn/")
        # LEVEL_META titles defined in src/services/paths.py
        assert "Absolute Beginner" in response.text  # A0
        assert "Beginner" in response.text  # A1

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_contains_your_path_section(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Response should contain the 'Your Path' section heading."""
        response = test_client.get("/learn/")
        assert "Your Path" in response.text

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_contains_progress_indicators(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Response should contain progress indicators with 0% for empty progress."""
        response = test_client.get("/learn/")
        assert "0%" in response.text

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_contains_back_link_to_lessons(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Response should contain a link back to the lessons list."""
        response = test_client.get("/learn/")
        assert "/lessons/" in response.text

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_page_title_includes_language(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """HTML title should include the language name."""
        response = test_client.get("/learn/")
        assert "Spanish Learning Path" in response.text


# =============================================================================
# GET /learn/recommendation -- HTMX Partial
# =============================================================================


class TestLearnRecommendationRoute:
    """Tests for GET /learn/recommendation endpoint (HTMX partial)."""

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_returns_200(self, mock_data: MagicMock, test_client: TestClient) -> None:
        """GET /learn/recommendation should return 200 OK."""
        response = test_client.get("/learn/recommendation")
        assert response.status_code == 200

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_returns_html_content(self, mock_data: MagicMock, test_client: TestClient) -> None:
        """Recommendation endpoint should return HTML content."""
        response = test_client.get("/learn/recommendation")
        assert "text/html" in response.headers["content-type"]

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_returns_partial_not_full_page(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Recommendation should return an HTML partial, not a full page."""
        response = test_client.get("/learn/recommendation")
        # The partial template does not extend base.html, so no DOCTYPE
        assert "<!DOCTYPE html>" not in response.text

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_contains_suggestion_text(self, mock_data: MagicMock, test_client: TestClient) -> None:
        """Recommendation partial should contain the suggestion text.

        With empty progress data the adaptive service produces a fallback
        suggestion that includes a 'Continue with' or 'keep exploring' message.
        """
        response = test_client.get("/learn/recommendation")
        text = response.text
        # With empty completed_lessons the next lesson exists, so
        # suggestion_text contains "Continue with" or the fallback message
        has_suggestion = "Continue with" in text or "keep exploring" in text or "Today" in text
        assert has_suggestion

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_language_parameter_respected(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Recommendation should use the language query parameter."""
        response = test_client.get("/learn/recommendation?language=de")
        assert response.status_code == 200


# =============================================================================
# Guest / Unauthenticated Access
# =============================================================================


class TestLearnPageWithoutAuth:
    """Tests for learn routes when the user is a guest (no auth, no cookies).

    The test_client fixture overrides OptionalUserDep to return mock_user.
    These tests verify the page still renders correctly with empty progress,
    as a proxy for the guest experience (path structure visible, no DB data).
    """

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_guest_sees_path_structure(self, mock_data: MagicMock, test_client: TestClient) -> None:
        """Guest user should still see the path structure with a 200 response."""
        response = test_client.get("/learn/")
        assert response.status_code == 200
        assert "Your Path" in response.text

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_path_timeline_rendered_without_progress(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Path timeline units should render even without progress data."""
        response = test_client.get("/learn/")
        assert "Absolute Beginner" in response.text
        assert "Beginner" in response.text

    @patch(f"{_LEARN_MODULE}._get_user_learning_data", return_value=([], [], 0))
    def test_browse_all_lessons_link_present(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Footer 'browse all lessons' link should be present."""
        response = test_client.get("/learn/")
        assert "browse all lessons" in response.text.lower()


# =============================================================================
# Error Handling
# =============================================================================


class TestLearnPageErrorHandling:
    """Tests for graceful degradation when _get_user_learning_data fails."""

    @patch(
        f"{_LEARN_MODULE}._get_user_learning_data",
        side_effect=Exception("Supabase connection error"),
    )
    def test_db_error_still_returns_200(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Page should render with empty progress when DB call fails.

        The route has a try/except around _get_user_learning_data and falls
        back to path_progress with an empty completed_lessons list.
        """
        response = test_client.get("/learn/")
        assert response.status_code == 200

    @patch(
        f"{_LEARN_MODULE}._get_user_learning_data",
        side_effect=Exception("Supabase connection error"),
    )
    def test_db_error_shows_path_structure(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Even on DB failure the path timeline should still be visible."""
        response = test_client.get("/learn/")
        assert "Your Path" in response.text
        assert "Absolute Beginner" in response.text

    @patch(
        f"{_LEARN_MODULE}._get_user_learning_data",
        side_effect=Exception("Supabase timeout"),
    )
    def test_recommendation_db_error_returns_200(
        self, mock_data: MagicMock, test_client: TestClient
    ) -> None:
        """Recommendation partial should still return 200 on DB error."""
        response = test_client.get("/learn/recommendation")
        assert response.status_code == 200
