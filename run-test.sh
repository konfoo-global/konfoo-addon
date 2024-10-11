#!/usr/bin/env bash
set -e

REPO_ROOT=$(cd "$(dirname "$0")"; pwd)
RED='\e[31m'
GREEN='\e[32m'
NC='\e[0m'
BOLD='\e[1m'
DARK_GRAY='\e[90m'
YELLOW='\e[33m'

USAGE=$(cat <<-END
Usage: $(basename "$0") [options] [LEVEL] <module name> [branch] <test method>
    Options:
        -h --help           Display this help
        --no-pull           Don't pull new images before setup
        -l --log-level      Set log level (default: INFO)

END
)

validate_and_check_log_level () {
    if [ -z "$1" ]; then
        echo "Missing log level"
        exit 1
    fi
    case $(echo $1 | tr '[:lower:]' '[:upper:]') in
        DEBUG|INFO|WARNING|ERROR|CRITICAL)
            LOG_LEVEL=$(echo $1 | tr '[:lower:]' '[:upper:]')
            ;;
        *)
            echo "Unknown log level: $1"
            exit 1
            ;;
    esac
}

POSITIONAL_ARGS=()
OPT_NO_PULL=false
LOG_TERMINAL_OUTPUT=/dev/null
LOG_LEVEL="INFO"

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-pull)
            OPT_NO_PULL=true
            shift
            ;;
        -l|--log-level)
            validate_and_check_log_level "$2"
            shift 2
            ;;
        -f|--foreground)
            LOG_TERMINAL_OUTPUT=/dev/stdout
            shift
            ;;
        -h|--help)
            echo "$USAGE"
            exit 0
            ;;
        -*)
            echo "Unknown option $1 - use -h for help"
            exit 1
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done
set -- "${POSITIONAL_ARGS[@]}" # restore positional args

usage () {
    echo "$USAGE"
}

[ $# -eq 0 ] && { usage; exit 1; }

TEST_MODULE="$1"
TARGET_BRANCH=$2
TEST_METHOD="$3"
if [ -z "$TARGET_BRANCH" ]; then
    TARGET_BRANCH=$(git symbolic-ref --short HEAD)
fi

declare -A odoo_images
odoo_images[edge]="ghcr.io/avalahee/edge-ee:latest"
odoo_images[18.0]="ghcr.io/avalahee/v18ee:latest"
odoo_images[17.0]="ghcr.io/avalahee/v17ee:latest"
odoo_images[16.0]="ghcr.io/avalahee/v16ee:latest"
ODOO_IMAGE=${ODOO_IMAGE:-${odoo_images[$TARGET_BRANCH]}}

if [ -z "$ODOO_IMAGE" ]; then
    echo -e "${RED}[!]${NC} No image specified for branch: $TARGET_BRANCH"
    exit 1
fi

echo -e "[+] Targeting: ${BOLD}${GREEN}$TARGET_BRANCH${NC}"
echo -e "[+] Running: ${BOLD}${GREEN}$ODOO_IMAGE${NC}"

if [ "$OPT_NO_PULL" = false ] ; then
    echo -e "[+] Pulling images"
    set -x
    docker pull postgres:latest
    docker pull "$ODOO_IMAGE"
    { set +x; } 2>/dev/null
    echo
fi

TARGET_VER_NAME=${TARGET_BRANCH/\.0/}
RUN_FOLDER_NAME="test_$(date +'%y-%m-%d_%H-%M-%S')"
TEST_RUN_DIR="${REPO_ROOT%%/}/test_runs/$RUN_FOLDER_NAME/$TARGET_VER_NAME"
LOG_OUTPUT_INSTALL="${TEST_RUN_DIR}/${TEST_MODULE}.install.log"
LOG_OUTPUT_TESTS="${TEST_RUN_DIR}/${TEST_MODULE}.test.log"

echo -e "[+] Output: ${GREEN}$RUN_FOLDER_NAME${NC}"

# construct docker volumes argument
volumes=""

# mount all modules in this repo
for path in $(find . -type f -name '__manifest__.py' -not -path '*/.*' -exec dirname "$1" {} + | sort | uniq)
do
    if [ "$path" = "." ]; then
        continue
    fi
    module_name=$(basename "$path")
    host_path=$(realpath "${REPO_ROOT%%/}/$path")
    mnt_path="/mnt/extra-addons/$module_name"
    volumes=$(printf "%s -v %s:%s" "$volumes" "$host_path" "$mnt_path");
done

determine_log_state () {
    set +e
    local result="OK"
    if grep -q 'WARNING' "$1"; then
        result="WARNING"
    fi
    if grep -q 'ERROR\|CRITICAL' "$1"; then
        result="ERROR"
    fi
    if grep -q 'FAIL' "$1"; then
        result="FAIL"
    fi
    echo "$result"
    set -e
}

# Run containers

cd "$REPO_ROOT"
mkdir -p "$TEST_RUN_DIR"

echo -e "[+] Testing: ${BOLD}${GREEN}$TEST_MODULE${NC}"
echo -e "${DARK_GRAY} -> starting postgres${NC}"
# version specific pg name
CONTAINER_PG_NAME=$(echo "ci-odoo-pg_$TARGET_BRANCH" | sed 's/\.0//')
CONTAINER_PG=$(docker run -d --rm --name "$CONTAINER_PG_NAME" \
    -e POSTGRES_PASSWORD=odoo \
    -e POSTGRES_USER=odoo \
    --tmpfs /var/lib/postgresql/data \
    "postgres:latest")
DB_HOST=$(docker inspect -f '{{ .NetworkSettings.IPAddress }}' "$CONTAINER_PG")
echo -e "${DARK_GRAY} -> postgres running as: $CONTAINER_PG ($DB_HOST)${NC}"

echo -e "${DARK_GRAY} -> running install: ${GREEN}$TEST_MODULE${NC}"
# shellcheck disable=SC2086
CONTAINER_NAME=$(echo "ci-odoo_$TARGET_BRANCH" | sed 's/\.0//')
docker run --rm -it --name "$CONTAINER_NAME" \
    -e HOST="$DB_HOST" \
    $volumes \
    --tmpfs /var/lib/odoo/filestore \
    $ODOO_IMAGE \
    -d dev \
    -i "$TEST_MODULE" --stop-after-init | tee "$LOG_OUTPUT_INSTALL" > "$LOG_TERMINAL_OUTPUT"

INSTALL_STATE=$(determine_log_state "$LOG_OUTPUT_INSTALL")
if [ "$INSTALL_STATE" = "OK" ]; then
    echo -e "${GREEN} -> install - ${BOLD}OK${NC}"
elif [ "$INSTALL_STATE" = "WARNING" ]; then
    echo -e "${YELLOW} -> install - ${BOLD}WARNING${NC}"
else
    echo -e "${RED} -> install - ${BOLD}ERROR${NC}"
fi

if [ "$INSTALL_STATE" = "OK" ] || [ "$INSTALL_STATE" = "WARNING" ]; then
    if [ "$TEST_METHOD" ]; then
        echo -e "${DARK_GRAY} -> running test: ${GREEN}$TEST_METHOD${NC}"
        # shellcheck disable=SC2086
        docker run --rm -it --name "$CONTAINER_NAME" \
            -e HOST="$DB_HOST" \
            $volumes \
            --tmpfs /var/lib/odoo/filestore \
            $ODOO_IMAGE \
            -d dev \
            --test-tags ".$TEST_METHOD" --stop-after-init \
            --log-handler odoo.addons."$TEST_MODULE:$LOG_LEVEL" | tee "$LOG_OUTPUT_TESTS" > "$LOG_TERMINAL_OUTPUT"
    else
        echo -e "${DARK_GRAY} -> running tests: ${GREEN}$TEST_MODULE${NC}"
        # shellcheck disable=SC2086
        docker run --rm -it --name "$CONTAINER_NAME" \
            -e HOST="$DB_HOST" \
            $volumes \
            --tmpfs /var/lib/odoo/filestore \
            $ODOO_IMAGE \
            -d dev \
            --test-tags "/$TEST_MODULE" --stop-after-init \
            --log-handler odoo.addons."$TEST_MODULE:$LOG_LEVEL" | tee "$LOG_OUTPUT_TESTS" > "$LOG_TERMINAL_OUTPUT"
    fi

    TEST_STATE=$(determine_log_state "$LOG_OUTPUT_TESTS")
    if [ "$TEST_STATE" = "OK" ]; then
        echo -e "${GREEN} -> tests - ${BOLD}OK${NC}"
    elif [ "$TEST_STATE" = "WARNING" ]; then
        echo -e "${YELLOW} -> tests - ${BOLD}WARNING${NC}"
    elif [ "$TEST_STATE" = "FAIL" ]; then
        echo -e "${RED} -> tests - ${BOLD}FAILED${NC}"
    else
        echo -e "${RED} -> tests - ${BOLD}ERROR${NC}"
    fi
else
    echo -e "${YELLOW} -> not running tests because install failed${NC}"
fi

echo -e "${DARK_GRAY} -> stopping postgres${NC}"
docker stop "$CONTAINER_PG" > /dev/null
echo -e "${DARK_GRAY} -> postgres stopped${NC}"

echo -e "[+] Completed"
