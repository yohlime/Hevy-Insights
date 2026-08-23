"""Hevy API client."""

import requests
import logging
from os import getenv
from typing import Any, cast
from dotenv import load_dotenv

from app.schemas.hevy import HevyUser

### ============================================================================

load_dotenv()  # Load environment variables from .env file

JsonDict = dict[str, Any]


class HevyOAuthConfig:
    """Configuration for Hevy's OAuth/free API endpoints."""

    def __init__(self):
        self.base_url: str = "https://api.hevyapp.com"
        x_api_key = getenv("X_API_KEY")  # Static for all users (free API)
        if not x_api_key:
            raise ValueError("X_API_KEY environment variable is required")
        self.x_api_key: str = x_api_key

    @property
    def login_url(self) -> str:
        return f"{self.base_url}/login"

    @property
    def refresh_token_url(self) -> str:
        """OAuth2 token refresh endpoint."""
        return f"{self.base_url}/refresh_token"

    @property
    def create_saved_account_url(self) -> str:
        return f"{self.base_url}/auth/create_saved_account"

    @property
    def login_with_saved_account_url(self) -> str:
        return f"{self.base_url}/login_with_saved_account"

    @property
    def user_account_url(self) -> str:
        return f"{self.base_url}/user/account"

    @property
    def user_workouts_paged_url(self) -> str:
        return f"{self.base_url}/user_workouts_paged"

    @property
    def workout_count_url(self) -> str:
        return f"{self.base_url}/workout_count"

    @property
    def body_measurements_url(self) -> str:
        return f"{self.base_url}/body_measurements"


class HevyAPIKeyConfig:
    """Configuration for Hevy's API-key endpoints."""

    def __init__(self):
        self.base_url: str = "https://api.hevyapp.com"

    @property
    def workouts_url(self) -> str:
        return f"{self.base_url}/v1/workouts"

    @property
    def workout_count_url(self) -> str:
        return f"{self.base_url}/v1/workouts/count"

    @property
    def user_info_url(self) -> str:
        return f"{self.base_url}/v1/user/info"

    @property
    def body_measurements_url(self) -> str:
        return f"{self.base_url}/v1/body_measurements"


### Main OAuth/free API client class
class HevyOAuthClient:
    """
    Client for Hevy's OAuth/free API used by username/password login.
    """

    def __init__(self, access_token: str | None = None, config: HevyOAuthConfig | None = None):
        self.access_token = access_token  # OAuth2 access token
        self.config = config or HevyOAuthConfig()
        self.session = requests.Session()

        if access_token:
            self._update_headers()

    def _update_headers(self) -> None:
        """
        Update session headers with current OAuth2 Bearer token.
        """
        headers = {
            "Content-Type": "application/json",
        }

        if self.access_token:
            headers["x-api-key"] = self.config.x_api_key
            headers["Authorization"] = f"Bearer {self.access_token}"

        self.session.headers.update(headers)

    ### ========== Free Hevy API Methods ==========

    def login(self, email_or_username: str, password: str, recaptcha_token: str) -> HevyUser:
        """
        Login with OAuth2 and reCAPTCHA token.

        Args:
            email_or_username: User's email or username
            password: User's password
            recaptcha_token: reCAPTCHA v3 Enterprise token

        Returns:
            HevyUser: User data with OAuth2 tokens

        Raises:
            HevyError: If login fails or returns unexpected response
        """
        logging.debug(f"Attempting OAuth2 login for user: {email_or_username}")

        headers = {"x-api-key": self.config.x_api_key, "Content-Type": "application/json", "Hevy-Platform": "web"}

        body = {"emailOrUsername": email_or_username, "password": password, "recaptchaToken": recaptcha_token, "useAuth2_0": True}

        try:
            response = self.session.post(self.config.login_url, headers=headers, json=body, timeout=30)
            response.raise_for_status()

            data = cast(JsonDict, response.json())

            ### Extract response and validate
            access_token = data.get("access_token") or data.get("auth_token")  # fallback
            refresh_token = data.get("refresh_token")

            ### Validate response
            if not access_token or not refresh_token:
                logging.error(f"Missing access/refresh token in response. Keys: {list(data.keys())}")
                raise HevyError("Login response missing access/refresh token")

            ### Update client's access token and headers after successful login
            self.access_token = access_token
            self._update_headers()
            user_id = data.get("user_id")

            return HevyUser(
                access_token=access_token,
                user_id=user_id if isinstance(user_id, str) else "",
                username=email_or_username if "@" not in email_or_username else None,
                email=email_or_username if "@" in email_or_username else None,
                refresh_token=refresh_token,
                expires_at=data.get("expires_at"),
            )

        except requests.JSONDecodeError as e:
            logging.error(f"JSON decode error during login: {e}")
            raise HevyError(f"JSON decode error occurred: {e}")
        except requests.HTTPError as e:
            logging.error(f"HTTP error during login: {e}")
            if e.response.status_code == 401:
                raise HevyError("Invalid credentials")
            elif e.response.status_code == 400:
                raise HevyError(f"Bad request: {e.response.text[:200]}")
            raise HevyError(f"HTTP error occurred: {e}")
        except requests.ConnectionError as e:
            logging.error(f"Connection error during login: {e}")
            raise HevyError(f"Connection error occurred: {e}")
        except requests.Timeout as e:
            logging.error(f"Timeout error during login: {e}")
            raise HevyError(f"Request timed out: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during login: {e}")
            raise HevyError(f"Unexpected error occurred: {e}")

    def create_saved_account(self) -> str:
        """Create a saved-account secret for future browser-login sessions."""
        if not self.access_token:
            raise HevyError("No access token available. Please login first.")

        headers = {
            "x-api-key": self.config.x_api_key,
            "Content-Type": "application/json",
            "Hevy-Platform": "web",
            "auth-token": self.access_token,
            "Authorization": f"Bearer {self.access_token}",
        }

        try:
            response = self.session.post(self.config.create_saved_account_url, headers=headers, timeout=30)
            response.raise_for_status()

            data = cast(JsonDict, response.json())
            secret = data.get("secret")
            if not isinstance(secret, str) or not secret:
                logging.error(f"Missing saved-account secret in response. Keys: {list(data.keys())}")
                raise HevyError("Saved-account response missing secret")

            return secret

        except requests.JSONDecodeError as e:
            logging.error(f"JSON decode error creating saved account: {e}")
            raise HevyError(f"JSON decode error occurred: {e}")
        except requests.HTTPError as e:
            logging.error(f"HTTP error creating saved account: {e}")
            raise HevyError(f"Saved-account creation failed: {e}")
        except requests.RequestException as e:
            logging.error(f"Request error creating saved account: {e}")
            raise HevyError(f"Saved-account creation failed: {e}")

    def login_with_saved_account(self, user_id: str, secret: str) -> HevyUser:
        """Login using a saved-account secret."""
        logging.debug("Logging in with Hevy saved account...")

        headers = {"x-api-key": self.config.x_api_key, "Content-Type": "application/json", "Hevy-Platform": "web"}
        body = {"userId": user_id, "secret": secret}

        try:
            response = self.session.post(self.config.login_with_saved_account_url, headers=headers, json=body, timeout=30)
            response.raise_for_status()

            data = cast(JsonDict, response.json())
            access_token = data.get("access_token") or data.get("auth_token")
            refresh_token = data.get("refresh_token")
            response_user_id = data.get("user_id")

            if not isinstance(access_token, str) or not access_token:
                logging.error(f"Missing access token in saved-account response. Keys: {list(data.keys())}")
                raise HevyError("Saved-account login response missing access token")

            self.access_token = access_token
            self._update_headers()

            return HevyUser(
                access_token=access_token,
                user_id=response_user_id if isinstance(response_user_id, str) else user_id,
                refresh_token=refresh_token if isinstance(refresh_token, str) else None,
                expires_at=data.get("expires_at"),
            )

        except requests.JSONDecodeError as e:
            logging.error(f"JSON decode error during saved-account login: {e}")
            raise HevyError(f"JSON decode error occurred: {e}")
        except requests.HTTPError as e:
            logging.error(f"HTTP error during saved-account login: {e}")
            if e.response.status_code in (400, 401, 404):
                raise HevyError("Invalid or expired saved-account secret")
            raise HevyError(f"Saved-account login failed: {e}")
        except requests.RequestException as e:
            logging.error(f"Request error during saved-account login: {e}")
            raise HevyError(f"Saved-account login failed: {e}")

    def refresh_access_token(self, refresh_token: str) -> HevyUser:
        """
        Refresh OAuth2 access token using refresh token.

        Args:
            refresh_token: The refresh token from previous login

        Returns:
            HevyUser: User data with new OAuth2 tokens

        Raises:
            HevyError: If refresh fails
        """
        logging.debug("Refreshing OAuth2 access token...")

        headers = {"x-api-key": self.config.x_api_key, "Content-Type": "application/json", "Hevy-Platform": "web"}

        body = {"refresh_token": refresh_token}

        try:
            response = self.session.post(self.config.refresh_token_url, headers=headers, json=body, timeout=30)
            response.raise_for_status()

            data = cast(JsonDict, response.json())

            ### Extract response and validate
            access_token = data.get("access_token") or data.get("auth_token")  # fallback
            new_refresh_token = data.get("refresh_token")

            ### Validate response
            if not access_token or not new_refresh_token:
                logging.error(f"Missing access/refresh token in response. Keys: {list(data.keys())}")
                raise HevyError("Login response missing access/refresh token")

            ### Update client's access token and headers after successful login
            self.access_token = access_token
            self._update_headers()
            user_id = data.get("user_id")

            return HevyUser(
                access_token=access_token,
                user_id=user_id if isinstance(user_id, str) else "",
                refresh_token=new_refresh_token,
                expires_at=data.get("expires_at"),
            )

        except requests.HTTPError as e:
            logging.error(f"HTTP error during token refresh: {e}")
            logging.error(f"Response status: {e.response.status_code}")
            if e.response.status_code == 401:
                raise HevyError("Invalid or expired refresh token")
            raise HevyError(f"Token refresh failed: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during token refresh: {e}")
            raise HevyError(f"Unexpected error occurred: {e}")

    def get_user_account(self) -> JsonDict:
        """
        Fetch user account information.

        Returns:
            dict | None: User account data if successful, None otherwise

        Raises:
            HevyError: If API request fails
        """
        logging.debug("Fetching user account information...")

        if not self.access_token:
            raise HevyError("No access token available. Please login first.")

        try:
            response = self.session.get(self.config.user_account_url, timeout=30)
            response.raise_for_status()

            data = cast(JsonDict, response.json())
            logging.debug(f"Successfully fetched account for user: {data.get('username')}")
            return data

        except requests.JSONDecodeError as e:
            logging.error(f"JSON decode error fetching user account: {e}")
            raise HevyError(f"JSON decode error occurred: {e}")
        except requests.HTTPError as e:
            logging.error(f"HTTP error fetching user account: {e}")
            if e.response.status_code == 401:
                raise HevyError("Unauthorized - Invalid or expired access token")
            raise HevyError(f"HTTP error occurred: {e}")
        except requests.ConnectionError as e:
            logging.error(f"Connection error fetching user account: {e}")
            raise HevyError(f"Connection error occurred: {e}")
        except requests.Timeout as e:
            logging.error(f"Timeout error fetching user account: {e}")
            raise HevyError(f"Request timed out: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching user account: {e}")
            raise HevyError(f"Unexpected error occurred: {e}")

    def get_workouts(self, username: str, offset: int = 0) -> JsonDict:
        """
        Fetch paginated workouts from Hevy API.

        Args:
            username: Username to filter workouts
            offset: Pagination offset (increments by 5: 0, 5, 10, 15, ...)

        Returns:
            dict: Workouts data containing 'workouts' key with list of workout objects

        Raises:
            HevyError: If API request fails
        """
        logging.debug(f"Fetching workouts ({username=}, {offset=})")

        if not self.access_token:
            raise HevyError("No access token available. Please login first.")

        params = {"offset": offset, "username": username}

        try:
            response = self.session.get(self.config.user_workouts_paged_url, params=params, timeout=30)
            response.raise_for_status()

            data = cast(JsonDict, response.json())
            workout_count = len(data.get("workouts", []))
            logging.debug(f"Successfully fetched {workout_count} workouts")
            return data

        except requests.JSONDecodeError as e:
            logging.error(f"JSON decode error fetching workouts: {e}")
            raise HevyError(f"JSON decode error occurred: {e}")
        except requests.HTTPError as e:
            logging.error(f"HTTP error fetching workouts: {e}")
            if e.response.status_code == 401:
                raise HevyError("Unauthorized - Invalid or expired access token")
            raise HevyError(f"HTTP error occurred: {e}")
        except requests.ConnectionError as e:
            logging.error(f"Connection error fetching workouts: {e}")
            raise HevyError(f"Connection error occurred: {e}")
        except requests.Timeout as e:
            logging.error(f"Timeout error fetching workouts: {e}")
            raise HevyError(f"Request timed out: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching workouts: {e}")
            raise HevyError(f"Unexpected error occurred: {e}")

    def get_workout_count(self, username: str) -> int:
        """Fetch total OAuth workout count for a user."""
        logging.debug(f"Fetching workout count ({username=})")

        if not self.access_token:
            raise HevyError("No access token available. Please login first.")

        try:
            response = self.session.get(self.config.workout_count_url, params={"username": username}, timeout=30)
            response.raise_for_status()

            count = _extract_workout_count(response.json())
            if count is None:
                raise HevyError("Workout count response missing count")
            return count

        except requests.JSONDecodeError as e:
            logging.error(f"JSON decode error fetching workout count: {e}")
            raise HevyError(f"JSON decode error occurred: {e}")
        except requests.HTTPError as e:
            logging.error(f"HTTP error fetching workout count: {e}")
            if e.response.status_code == 401:
                raise HevyError("Unauthorized - Invalid or expired access token")
            raise HevyError(f"HTTP error occurred: {e}")
        except requests.RequestException as e:
            logging.error(f"Request error fetching workout count: {e}")
            raise HevyError(f"Request error occurred: {e}")

    def get_body_measurements(self) -> list[JsonDict]:
        """
        Fetch body measurements from Hevy API.

        Returns:
            list: Body measurements data (list of dicts with id, weight_kg, date, created_at)

        Raises:
            HevyError: If API request fails
        """
        logging.debug("Fetching body measurements")

        if not self.access_token:
            raise HevyError("No access token available. Please login first.")

        try:
            response = self.session.get(self.config.body_measurements_url, timeout=30)
            response.raise_for_status()

            data = cast(list[JsonDict], response.json())
            logging.debug(f"Successfully fetched {len(data)} body measurements")
            return data

        except requests.JSONDecodeError as e:
            logging.error(f"JSON decode error fetching body measurements: {e}")
            raise HevyError(f"JSON decode error occurred: {e}")
        except requests.HTTPError as e:
            logging.error(f"HTTP error fetching body measurements: {e}")
            if e.response.status_code == 401:
                raise HevyError("Unauthorized - Invalid or expired access token")
            raise HevyError(f"HTTP error occurred: {e}")
        except requests.ConnectionError as e:
            logging.error(f"Connection error fetching body measurements: {e}")
            raise HevyError(f"Connection error occurred: {e}")
        except requests.Timeout as e:
            logging.error(f"Timeout error fetching body measurements: {e}")
            raise HevyError(f"Request timed out: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching body measurements: {e}")
            raise HevyError(f"Unexpected error occurred: {e}")

    def post_body_measurements(self, date: str, weight_kg: float) -> dict[str, bool]:
        """
        Post body measurements to Hevy API.

        Args:
            date: Date of the measurement in ISO 8601 format (YYYY-MM-DD)
            weight_kg: Weight in kilograms

        Raises:
            HevyError: If API request fails
        """
        logging.debug(f"Posting body measurement: {date=}, {weight_kg=}")

        if not self.access_token:
            raise HevyError("No access token available. Please login first.")

        try:
            body = {"measurementsBatch": [{"date": date, "weight_kg": weight_kg, "_unsyncedObjectId": "zitronenkuchen"}]}

            response = self.session.post(f"{self.config.body_measurements_url}_batch", json=body, timeout=30)
            response.raise_for_status()

            logging.debug("Successfully posted body measurement")
            return {"success": True}

        except requests.HTTPError as e:
            logging.error(f"HTTP error posting body measurements: {e}")
            if e.response.status_code == 401:
                raise HevyError("Unauthorized - Invalid or expired access token")
            raise HevyError(f"HTTP error occurred: {e}")
        except requests.ConnectionError as e:
            logging.error(f"Connection error posting body measurements: {e}")
            raise HevyError(f"Connection error occurred: {e}")
        except requests.Timeout as e:
            logging.error(f"Timeout error posting body measurements: {e}")
            raise HevyError(f"Request timed out: {e}")
        except Exception as e:
            logging.error(f"Unexpected error posting body measurements: {e}")
            raise HevyError(f"Unexpected error occurred: {e}")

### Hevy API-key client class
class HevyAPIKeyClient:
    """Client for Hevy's API-key endpoints."""

    def __init__(self, api_key: str, config: HevyAPIKeyConfig | None = None):
        self.api_key = api_key
        self.config = config or HevyAPIKeyConfig()
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json", "api-key": self.api_key})

    ### ========== Hevy API-key Methods ==========

    def get_user_account(self) -> JsonDict:
        """Fetch authenticated API-key user information."""
        logging.debug("Fetching API-key user information...")

        try:
            response = self.session.get(self.config.user_info_url, timeout=30)
            response.raise_for_status()

            data = cast(JsonDict, response.json())
            user_data = data.get("data")
            if isinstance(user_data, dict):
                return user_data
            return data

        except requests.JSONDecodeError as e:
            logging.error(f"JSON decode error fetching API-key user info: {e}")
            raise HevyError(f"JSON decode error occurred: {e}")
        except requests.HTTPError as e:
            logging.error(f"HTTP error fetching API-key user info: {e}")
            if e.response.status_code == 401:
                raise HevyError("Unauthorized - Invalid API key")
            if e.response.status_code == 404:
                raise HevyError("User not found")
            raise HevyError(f"HTTP error occurred: {e}")
        except requests.RequestException as e:
            logging.error(f"Request error fetching API-key user info: {e}")
            raise HevyError(f"Request error occurred: {e}")

    def get_body_measurements(self) -> list[JsonDict]:
        """Fetch all PRO body measurements and return the frontend-compatible list shape."""
        logging.debug("Fetching PRO body measurements...")

        measurements: list[JsonDict] = []
        page = 1
        page_size = 10

        while True:
            try:
                response = self.session.get(
                    self.config.body_measurements_url,
                    params={"page": page, "pageSize": page_size},
                    timeout=30,
                )
                response.raise_for_status()

                data = cast(JsonDict, response.json())
                batch = data.get("body_measurements")
                if not isinstance(batch, list) or not batch:
                    return measurements

                measurements.extend(measurement for measurement in batch if isinstance(measurement, dict))
                page_count = data.get("page_count")
                if isinstance(page_count, int) and page >= page_count:
                    return measurements
                page += 1

            except requests.JSONDecodeError as e:
                logging.error(f"JSON decode error fetching PRO body measurements: {e}")
                raise HevyError(f"JSON decode error occurred: {e}")
            except requests.HTTPError as e:
                logging.error(f"HTTP error fetching PRO body measurements: {e}")
                if e.response.status_code == 401:
                    raise HevyError("Unauthorized - Invalid API key")
                if e.response.status_code == 404:
                    return measurements
                raise HevyError(f"HTTP error occurred: {e}")
            except requests.RequestException as e:
                logging.error(f"Request error fetching PRO body measurements: {e}")
                raise HevyError(f"Request error occurred: {e}")

    def post_body_measurements(self, date: str, weight_kg: float) -> dict[str, bool]:
        """Create a PRO body measurement entry."""
        logging.debug(f"Posting PRO body measurement: {date=}, {weight_kg=}")

        try:
            response = self.session.post(
                self.config.body_measurements_url,
                json={"date": date, "weight_kg": weight_kg},
                timeout=30,
            )
            response.raise_for_status()
            return {"success": True}

        except requests.HTTPError as e:
            logging.error(f"HTTP error posting PRO body measurement: {e}")
            if e.response.status_code == 401:
                raise HevyError("Unauthorized - Invalid API key")
            if e.response.status_code == 409:
                raise HevyError("A body measurement for this date already exists")
            raise HevyError(f"HTTP error occurred: {e}")
        except requests.RequestException as e:
            logging.error(f"Request error posting PRO body measurement: {e}")
            raise HevyError(f"Request error occurred: {e}")

    def get_workouts(self, page: int = 1, page_size: int = 10) -> JsonDict:
        """
        Fetch paginated workouts from Hevy PRO API.

        Args:
            page: Page number (default: 1)
            page_size: Number of workouts per page (default: 10)

        Returns:
            dict: Workouts data containing 'workouts', 'page', 'page_count' keys

        Raises:
            HevyError: If API request fails
        """
        logging.debug(f"Fetching PRO workouts ({page=}, {page_size=})")

        if not self.api_key:
            raise HevyError("No PRO API key available. Please use a Hevy PRO API key.")

        params = {"page": page, "pageSize": page_size}

        try:
            response = self.session.get(self.config.workouts_url, params=params, timeout=30)
            response.raise_for_status()

            data = cast(JsonDict, response.json())
            workouts = cast(list[JsonDict], data.get("workouts", []))

            ### Transform PRO API format to match the frontend/free API shape.
            from datetime import datetime

            for workout in workouts:
                if not isinstance(workout, dict):
                    continue

                if "start_time" in workout and isinstance(workout["start_time"], str):
                    workout["start_time"] = int(datetime.fromisoformat(workout["start_time"].replace("Z", "+00:00")).timestamp())
                if "end_time" in workout and isinstance(workout["end_time"], str):
                    workout["end_time"] = int(datetime.fromisoformat(workout["end_time"].replace("Z", "+00:00")).timestamp())
                if "updated_at" in workout and isinstance(workout["updated_at"], str):
                    workout["updated_at"] = int(datetime.fromisoformat(workout["updated_at"].replace("Z", "+00:00")).timestamp())
                if "created_at" in workout and isinstance(workout["created_at"], str):
                    workout["created_at"] = int(datetime.fromisoformat(workout["created_at"].replace("Z", "+00:00")).timestamp())

                estimated_volume = 0
                for exercise_index, exercise in enumerate(workout.get("exercises", [])):
                    if not isinstance(exercise, dict):
                        continue

                    if "id" not in exercise:
                        exercise["id"] = f"{workout['id']}-ex-{exercise.get('index', exercise_index)}"

                    for set_index, set_data in enumerate(exercise.get("sets", [])):
                        if not isinstance(set_data, dict):
                            continue

                        if "id" not in set_data:
                            set_data["id"] = f"{exercise['id']}-set-{set_data.get('index', set_index)}"

                        weight = set_data.get("weight_kg") or 0
                        reps = set_data.get("reps") or 0
                        estimated_volume += weight * reps

                workout["estimated_volume_kg"] = estimated_volume

            workout_count = len(workouts)
            logging.debug(f"Successfully fetched {workout_count} PRO workouts")
            return {"workouts": workouts, "page": page, "page_size": page_size, "workout_count": workout_count}

        except requests.JSONDecodeError as e:
            logging.error(f"JSON decode error fetching PRO workouts: {e}")
            raise HevyError(f"JSON decode error occurred: {e}")
        except requests.HTTPError as e:
            logging.error(f"HTTP error fetching PRO workouts: {e}")
            if e.response.status_code == 401:
                raise HevyError("Unauthorized - Invalid API key")
            ### Handle 404 when no more workouts are available
            if e.response.status_code == 404:
                logging.debug(f"No workouts found on page {page} (404)")
                return {"workouts": [], "page": page, "page_size": page_size, "workout_count": 0}
            raise HevyError(f"HTTP error occurred: {e}")
        except requests.ConnectionError as e:
            logging.error(f"Connection error fetching PRO workouts: {e}")
            raise HevyError(f"Connection error occurred: {e}")
        except requests.Timeout as e:
            logging.error(f"Timeout error fetching PRO workouts: {e}")
            raise HevyError(f"Request timed out: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching PRO workouts: {e}")
            raise HevyError(f"Unexpected error occurred: {e}")

    def get_workout_count(self) -> int:
        """Fetch total workout count from the API-key endpoint."""
        logging.debug("Fetching API-key workout count")

        if not self.api_key:
            raise HevyError("No PRO API key available. Please use a Hevy PRO API key.")

        try:
            response = self.session.get(self.config.workout_count_url, timeout=30)
            response.raise_for_status()

            count = _extract_workout_count(response.json())
            if count is None:
                raise HevyError("Workout count response missing count")
            return count

        except requests.JSONDecodeError as e:
            logging.error(f"JSON decode error fetching API-key workout count: {e}")
            raise HevyError(f"JSON decode error occurred: {e}")
        except requests.HTTPError as e:
            logging.error(f"HTTP error fetching API-key workout count: {e}")
            if e.response.status_code == 401:
                raise HevyError("Unauthorized - Invalid API key")
            raise HevyError(f"HTTP error occurred: {e}")
        except requests.RequestException as e:
            logging.error(f"Request error fetching API-key workout count: {e}")
            raise HevyError(f"Request error occurred: {e}")

    def validate_api_key(self) -> bool:
        """
        Validate the Hevy PRO API key by attempting to fetch a single workout.

        Returns:
            bool: True if valid, False otherwise
        """
        logging.debug("Validating PRO API key...")

        if not self.api_key:
            logging.warning("No API key to validate")
            return False

        try:
            ### Try to fetch a single workout to validate the key
            response = self.session.get(self.config.workouts_url, params={"page": 1, "pageSize": 1})

            is_valid = response.status_code == 200
            logging.debug(f"PRO API key validation result: {is_valid}")
            return is_valid

        except requests.RequestException as e:
            logging.error(f"Error validating PRO API key: {e}")
            raise HevyError(f"PRO API key validation failed: {e}")


### ============================================================================


class HevyError(Exception):
    """Custom error for Hevy API operations."""

    pass


def _extract_workout_count(data: Any) -> int | None:
    if isinstance(data, bool):
        return None
    if isinstance(data, int):
        return data
    if isinstance(data, float):
        return int(data)
    if isinstance(data, str) and data.isdigit():
        return int(data)
    if not isinstance(data, dict):
        return None

    for key in ("workout_count", "workouts_count", "count", "total", "total_count"):
        count = _extract_workout_count(data.get(key))
        if count is not None:
            return count

    return _extract_workout_count(data.get("data"))
