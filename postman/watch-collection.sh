#!/bin/bash
# Postman Collection File Watcher
# Watches for changes to the Postman collection and notifies you to re-import

COLLECTION_FILE="postman/collections/GROSINT_V2_API.postman_collection.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FULL_COLLECTION_PATH="$PROJECT_ROOT/$COLLECTION_FILE"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📦 Postman Collection File Watcher${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""
echo -e "👀 Watching: ${GREEN}$FULL_COLLECTION_PATH${NC}"
echo ""
echo -e "${YELLOW}💡 Instructions:${NC}"
echo "   When the collection file changes, you'll be notified."
echo "   To sync changes in Postman:"
echo "   1. Open Postman"
echo "   2. Click 'Import' button"
echo "   3. Select: $COLLECTION_FILE"
echo "   4. Click 'Import' (this will update your collection)"
echo ""
echo -e "${GREEN}✅ Watcher started! Press Ctrl+C to stop${NC}"
echo ""

# Check if fswatch is installed
if ! command -v fswatch &> /dev/null; then
    echo -e "${YELLOW}⚠️  fswatch not found. Installing...${NC}"
    echo ""

    # Check if Homebrew is available
    if command -v brew &> /dev/null; then
        echo "Installing fswatch via Homebrew..."
        brew install fswatch
    else
        echo -e "${YELLOW}❌ Homebrew not found. Please install fswatch manually:${NC}"
        echo "   macOS: brew install fswatch"
        echo "   Linux: sudo apt-get install fswatch (or equivalent)"
        echo ""
        echo "Alternatively, you can manually check for changes and re-import when needed."
        exit 1
    fi
fi

# Watch for changes
fswatch -o "$FULL_COLLECTION_PATH" | while read f; do
    echo ""
    echo -e "${GREEN}🔄 Collection file changed at $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "   ${BLUE}File:${NC} $COLLECTION_FILE"
    echo ""
    echo -e "${YELLOW}📥 Action Required:${NC}"
    echo "   1. Open Postman"
    echo "   2. Click 'Import' → 'File'"
    echo "   3. Select: $FULL_COLLECTION_PATH"
    echo "   4. Click 'Import' to update your collection"
    echo ""

    # macOS notification (if available)
    if command -v osascript &> /dev/null; then
        osascript -e "display notification \"Postman collection updated! Please re-import.\" with title \"Postman Sync\" sound name \"Glass\""
    fi

    # Open Finder to the file location (macOS)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${BLUE}💡 Opening file location in Finder...${NC}"
        open -R "$FULL_COLLECTION_PATH"
    fi

    echo -e "${GREEN}✅ Ready for next change...${NC}"
    echo ""
done
