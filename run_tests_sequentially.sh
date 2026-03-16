#!/bin/bash

# Script to run all API endpoint tests sequentially to avoid system hangs
# Each test class is run separately with a small delay between them

echo "========================================="
echo "Running API Endpoint Tests Sequentially"
echo "========================================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter for passed/failed tests
PASSED=0
FAILED=0

# Function to run a test and track results
run_test() {
    local test_path=$1
    local test_name=$2
    
    echo -e "${YELLOW}Running: $test_name${NC}"
    echo "Command: pytest $test_path -v"
    echo ""
    
    if pytest "$test_path" -v; then
        echo -e "${GREEN}✓ PASSED: $test_name${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAILED: $test_name${NC}"
        ((FAILED++))
    fi
    
    echo ""
    echo "Waiting 2 seconds before next test..."
    sleep 2
    echo ""
}

# Test 1: Clip Reel Sharing
run_test "tracevision/tests/test_clip_reel_sharing.py::TestClipReelSharing" \
         "Clip Reel Sharing (POST /api/vision/clip-reels/{id}/share/)"

# Test 2: Shared By Me
run_test "tracevision/tests/test_clip_reel_sharing.py::TestListSharedReels" \
         "Shared By Me (GET /api/vision/clip-reels/shared-by-me/)"

# Test 3: Revoke Share
run_test "tracevision/tests/test_clip_reel_sharing.py::TestRevokeShare" \
         "Revoke Share (DELETE /api/vision/clip-reels/{id}/shares/{share_id}/)"

# Test 4: Clip Reel Comments
run_test "tracevision/tests/test_clip_reel_comments.py::TestClipReelComments" \
         "Clip Reel Comments (POST & GET /api/vision/clip-reels/{id}/comments/)"

# Test 5: Comment Likes
run_test "tracevision/tests/test_clip_reel_comments.py::TestCommentLikes" \
         "Comment Likes (POST & DELETE /api/vision/comments/{id}/like/)"

# Test 6: Highlight Notes Creation (Mocked)
run_test "tracevision/tests/test_highlight_notes_mocked.py::TestHighlightNotesCreateMocked" \
         "Highlight Notes Creation (POST /api/vision/highlights/{id}/notes/)"

# Test 7: Highlight Notes Listing (Mocked)
run_test "tracevision/tests/test_highlight_notes_mocked.py::TestHighlightNotesListMocked" \
         "Highlight Notes Listing (GET /api/vision/highlights/{id}/notes/)"

# Test 8: All Endpoints Mocked - Clip Reel Share
run_test "tracevision/tests/test_all_endpoints_mocked.py::TestClipReelShareMocked" \
         "All Endpoints - Clip Reel Share (Mocked)"

# Test 9: All Endpoints Mocked - Shared By Me
run_test "tracevision/tests/test_all_endpoints_mocked.py::TestClipReelSharedByMeMocked" \
         "All Endpoints - Shared By Me (Mocked)"

# Test 10: All Endpoints Mocked - Comments Create
run_test "tracevision/tests/test_all_endpoints_mocked.py::TestClipReelCommentsCreateMocked" \
         "All Endpoints - Comments Create (Mocked)"

# Test 11: All Endpoints Mocked - Comments List
run_test "tracevision/tests/test_all_endpoints_mocked.py::TestClipReelCommentsListMocked" \
         "All Endpoints - Comments List (Mocked)"

# Test 12: All Endpoints Mocked - Clip Reel List
run_test "tracevision/tests/test_all_endpoints_mocked.py::TestClipReelListMocked" \
         "All Endpoints - Clip Reel List (Mocked)"

# Test 13: All Endpoints Mocked - Highlight Notes Create
run_test "tracevision/tests/test_all_endpoints_mocked.py::TestHighlightNotesCreateMocked" \
         "All Endpoints - Highlight Notes Create (Mocked)"

# Test 14: All Endpoints Mocked - Highlight Notes List
run_test "tracevision/tests/test_all_endpoints_mocked.py::TestHighlightNotesListMocked" \
         "All Endpoints - Highlight Notes List (Mocked)"

# Summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo "Total: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the output above.${NC}"
    exit 1
fi
