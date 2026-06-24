#!/bin/bash
# NEXUS Backend Setup Verification Script
# Run this to verify your development environment is configured correctly

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "                    NEXUS BACKEND - SETUP VERIFICATION"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

CHECKS_PASSED=0
CHECKS_FAILED=0

check() {
    local description=$1
    local command=$2

    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $description"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}✗${NC} $description"
        ((CHECKS_FAILED++))
    fi
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check Python
echo "Checking Python Environment..."
check "Python installed" "python --version"
check "Requirements installed" "python -c 'import fastapi, sqlalchemy, anthropic, azure.storage.blob, azure.search.documents, azure.identity'"
echo ""

# Check .env files
echo "Checking Configuration Files..."
check ".env exists" "test -f .env"
check ".env.local exists" "test -f .env.local"
check ".env.local is executable" "test -r .env.local"
echo ""

# Check .env.local content
echo "Checking .env.local Configuration..."
check ".env.local has AZURE_TENANT_ID" "grep -q 'AZURE_TENANT_ID' .env.local"
check ".env.local has AZURE_CLIENT_ID" "grep -q 'AZURE_CLIENT_ID' .env.local"
check ".env.local has AZURE_CLIENT_SECRET" "grep -q 'AZURE_CLIENT_SECRET' .env.local"
check ".env.local has AZURE_KEY_VAULT_URL" "grep -q 'AZURE_KEY_VAULT_URL' .env.local"
check ".env.local has DATABASE_URL" "grep -q 'DATABASE_URL' .env.local"
check ".env.local has AZURE_STORAGE_ACCOUNT_NAME" "grep -q 'AZURE_STORAGE_ACCOUNT_NAME' .env.local"
echo ""

# Check .gitignore
echo "Checking Security (.gitignore)..."
check ".gitignore ignores .env.local" "grep -q '.env.local' .gitignore"
check ".env file has no secrets" "! grep -E 'sk-|qO|secret=|password=' .env | grep -v '^#'"
echo ""

# Check critical source files
echo "Checking Source Files..."
check "credential_provider.py exists" "test -f services/credential_provider.py"
check "main.py exists" "test -f main.py"
check "database.py exists" "test -f database.py"
check "requirements.txt has azure-keyvault-secrets" "grep -q 'azure-keyvault-secrets' requirements.txt"
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo -e "Results: ${GREEN}$CHECKS_PASSED passed${NC}, ${RED}$CHECKS_FAILED failed${NC}"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Your setup is ready.${NC}"
    echo ""
    echo "Next steps:"
    echo "  cd BACKEND"
    echo "  source .env.local"
    echo "  python -m uvicorn main:app --reload"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please review the output above.${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  - Make sure .env.local exists and is readable"
    echo "  - Run: pip install -r requirements.txt"
    echo "  - Check that all environment variables are set in .env.local"
    echo ""
    exit 1
fi
