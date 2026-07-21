"""Source-controlled NodeSeek site contract verified by docs/site-analysis.md."""

BASE_URL = "https://www.nodeseek.com"
STATUS_PATH = "/api/attendance/board?page=1"
ACTION_PATH = "/api/attendance?random=false"
RANDOM_ACTION_PATH = "/api/attendance?random=true"

ACTION_PATHS = {
    "fixed": ACTION_PATH,
    "random": RANDOM_ACTION_PATH,
}

FORBIDDEN_OVERRIDE_ENV_NAMES = (
    "CHECKIN_BASE_URL",
    "CHECKIN_STATUS_PATH",
    "CHECKIN_ACTION_PATH",
)
