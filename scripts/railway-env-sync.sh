#!/usr/bin/env zsh
# railway-env-sync.sh
# Syncs environment variables from .env to Railway
#
# Usage:
#   ./scripts/railway-env-sync.sh          # Dry run (shows what would be set)
#   ./scripts/railway-env-sync.sh --apply  # Actually set the variables
#   ./scripts/railway-env-sync.sh --help   # Show help

# Note: Not using set -e because arithmetic operations can return 1

# Store script path for use in functions
SCRIPT_PATH="./scripts/railway-env-sync.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables to SKIP (local-only, test, or not needed in production)
SKIP_PATTERNS=(
    "^LOCAL_"
    "^TEST_"
    "^REDIS_"           # Not using Redis in production (PGQueuer uses Postgres)
    "^CELERY_"          # Not using Celery (using PGQueuer)
    "^NEO4J_LOCAL_"     # Local Neo4j settings
    "^GMAIL_"           # Local file paths
    "^YOUTUBE_CREDENTIALS"
    "^YOUTUBE_TOKEN"
    "^RSS_FEEDS_FILE"
    "^DOCLING_CACHE_DIR"
    "^YOUTUBE_TEMP_DIR"
)

# Variables to TRANSFORM for production (associative array)
typeset -A TRANSFORMS
TRANSFORMS=(
    ENVIRONMENT "production"
    DATABASE_PROVIDER "supabase"
    NEO4J_PROVIDER "auradb"
    LOG_LEVEL "INFO"
)

# Help message
show_help() {
    echo "Usage: $SCRIPT_PATH [OPTIONS]"
    echo ""
    echo "Syncs environment variables from .env to Railway"
    echo ""
    echo "Options:"
    echo "  --apply     Actually set the variables in Railway"
    echo "  --dry-run   Show what would be set (default)"
    echo "  --help      Show this help message"
    echo ""
    echo "Prerequisites:"
    echo "  - Railway CLI installed (brew install railway)"
    echo "  - Logged in to Railway (railway login)"
    echo "  - Project linked (railway link)"
    echo "  - Service created and linked (railway service)"
    echo ""
    echo "Behavior:"
    echo "  - Skips local-only variables (LOCAL_*, TEST_*, REDIS_*, CELERY_*, etc.)"
    echo "  - Transforms ENVIRONMENT→production, DATABASE_PROVIDER→supabase, NEO4J_PROVIDER→auradb"
    echo "  - Masks sensitive values (PASSWORD, KEY, SECRET, TOKEN) in output"
    echo ""
    echo "Quick Start (if no service exists):"
    echo "  1. railway login          # Login to Railway"
    echo "  2. railway link           # Link to your project"
    echo "  3. railway up             # Deploy (creates service automatically)"
    echo "  4. railway service        # Link to the new service"
    echo "  5. $SCRIPT_PATH --apply             # Sync environment variables"
    echo "  6. railway up             # Redeploy with new variables"
}

# Check if a variable should be skipped
should_skip() {
    local var_name="$1"
    for pattern in "${SKIP_PATTERNS[@]}"; do
        if [[ "$var_name" =~ $pattern ]]; then
            return 0  # true, should skip
        fi
    done
    return 1  # false, don't skip
}

# Get transformed value or original
get_value() {
    local var_name="$1"
    local var_value="$2"

    if [[ -n "${TRANSFORMS[$var_name]}" ]]; then
        echo "${TRANSFORMS[$var_name]}"
    else
        echo "$var_value"
    fi
}

# Mask sensitive values for display
mask_value() {
    local var_name="$1"
    local var_value="$2"

    # Mask passwords, keys, secrets, tokens
    if [[ "$var_name" =~ (PASSWORD|KEY|SECRET|TOKEN) ]]; then
        if [[ ${#var_value} -gt 8 ]]; then
            echo "${var_value:0:4}****${var_value: -4}"
        else
            echo "****"
        fi
    else
        echo "$var_value"
    fi
}

# Main script
main() {
    local apply=false
    local env_file=".env"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --apply)
                apply=true
                shift
                ;;
            --dry-run)
                apply=false
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done

    # Check prerequisites
    if ! command -v railway &> /dev/null; then
        echo -e "${RED}Error: Railway CLI not installed${NC}"
        echo "Install with: brew install railway"
        exit 1
    fi

    if [[ ! -f "$env_file" ]]; then
        echo -e "${RED}Error: .env file not found${NC}"
        exit 1
    fi

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Railway Environment Variable Sync${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    if [[ "$apply" == true ]]; then
        echo -e "${YELLOW}Mode: APPLY (will set variables in Railway)${NC}"

        # Verify Railway is linked to a project
        if ! railway status &> /dev/null; then
            echo -e "${RED}Error: Not linked to a Railway project${NC}"
            echo ""
            echo "Run these commands first:"
            echo "  railway login    # Login to Railway"
            echo "  railway link     # Link to your project"
            exit 1
        fi

        # Check if a service is linked
        local service_status=$(railway status 2>&1)
        if echo "$service_status" | grep -q "Service: None"; then
            echo -e "${RED}Error: No service linked${NC}"
            echo ""
            echo -e "${YELLOW}You need to create and link a service first:${NC}"
            echo ""
            echo "  ${BLUE}Option 1: Deploy to create service automatically${NC}"
            echo "    railway up              # Creates service from Dockerfile"
            echo "    railway service         # Link to the new service"
            echo "    $SCRIPT_PATH --apply              # Then run this script again"
            echo "    railway up              # Redeploy with variables"
            echo ""
            echo "  ${BLUE}Option 2: Create empty service first${NC}"
            echo "    railway service create  # Create empty service"
            echo "    railway service         # Link to it"
            echo "    $SCRIPT_PATH --apply              # Sync variables"
            echo "    railway up              # Deploy"
            echo ""
            echo "  ${BLUE}Option 3: Via Railway Dashboard${NC}"
            echo "    1. Go to railway.app → Your project"
            echo "    2. Click '+ New Service' → 'Empty Service' or 'GitHub Repo'"
            echo "    3. Run: railway service   # Link to it locally"
            echo "    4. Run: $SCRIPT_PATH --apply"
            exit 1
        fi

        echo ""
    else
        echo -e "${GREEN}Mode: DRY RUN (showing what would be set)${NC}"
    fi
    echo ""

    local count=0
    local skipped=0
    local transformed=0

    # Read .env file line by line
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip empty lines and comments
        [[ -z "$line" ]] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue

        # Extract variable name and value (handle = in value)
        if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
            var_name="${match[1]}"
            var_value="${match[2]}"

            # Remove inline comments (but be careful with URLs containing #)
            # Only strip comments that have a space before #
            var_value="${var_value%%  #*}"
            var_value="${var_value%% #*}"

            # Remove surrounding quotes if present
            var_value="${var_value#\"}"
            var_value="${var_value%\"}"
            var_value="${var_value#\'}"
            var_value="${var_value%\'}"

            # Trim whitespace
            var_value="${var_value%% }"
            var_value="${var_value## }"

            # Skip empty values
            [[ -z "$var_value" ]] && continue

            # Skip if matches skip patterns
            if should_skip "$var_name"; then
                echo -e "  ${YELLOW}SKIP${NC} $var_name (local-only)"
                ((skipped++))
                continue
            fi

            # Get potentially transformed value
            final_value=$(get_value "$var_name" "$var_value")

            # Check if value was transformed
            local transform_note=""
            if [[ "$final_value" != "$var_value" ]]; then
                transform_note=" ${BLUE}(→ $final_value)${NC}"
                ((transformed++))
            fi

            # Display masked value
            masked=$(mask_value "$var_name" "$final_value")
            echo -e "  ${GREEN}SET${NC} $var_name=$masked$transform_note"

            # Actually set if applying
            if [[ "$apply" == true ]]; then
                if railway variables set "$var_name=$final_value" 2>/dev/null; then
                    : # success, do nothing
                else
                    echo -e "  ${RED}FAILED${NC} to set $var_name"
                fi
            fi

            ((count++))
        fi
    done < "$env_file"

    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "Summary:"
    echo -e "  Variables to set: ${GREEN}$count${NC}"
    echo -e "  Skipped (local): ${YELLOW}$skipped${NC}"
    echo -e "  Transformed: ${BLUE}$transformed${NC}"
    echo -e "${BLUE}========================================${NC}"

    if [[ "$apply" == false ]]; then
        echo ""
        echo -e "${YELLOW}This was a dry run. To apply changes, run:${NC}"
        echo -e "  ./scripts/railway-env-sync.sh --apply"
    else
        echo ""
        echo -e "${GREEN}Variables synced to Railway!${NC}"
        echo -e "Deploy with: ${BLUE}railway up${NC}"
    fi
}

main "$@"
