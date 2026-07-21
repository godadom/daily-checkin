"""Source-controlled NovalPie site contract verified by docs/site-analysis.md."""

BASE_URL = "https://novalpie.cc"
STATUS_PATH = "/api/users/me/checkins"
ACTION_PATH = "/api/users/me/checkins"

FORBIDDEN_OVERRIDE_ENV_NAMES = (
    "CHECKIN_BASE_URL",
    "CHECKIN_STATUS_PATH",
    "CHECKIN_ACTION_PATH",
)
